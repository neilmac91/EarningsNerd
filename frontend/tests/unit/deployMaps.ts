import { readdirSync, readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

/**
 * The deploy maps as the plan-claim gates read them: planLimitsLockstep.spec.ts (no deploy map sets
 * PRO_SUMMARY_MONTHLY_CAP, whose default the /pricing FAQ and the filing page's limit card state) and
 * changeReportPlanClaims.spec.tsx (production cannot serve ENABLE_SECTION_CHANGES's wording diff). One reading for
 * both, so a form one gate reads the other reads too; each spec keeps its own rule over the lines it is given, its
 * messages and its planted forms. Not a spec: a module the gates share.
 *
 * What it reads:
 *  - every workflow GitHub runs: each .yml or .yaml file directly under .github/workflows, by file name, as text;
 *  - the executable lines of those workflows that name a setting: each line whole, with its file and its 1-based
 *    number. A line whose first non-blank character is `#` is a comment and skipped; any other line that holds the
 *    name counts, whatever its form (an --update-env-vars, --set-env-vars or --update-secrets entry, an env: key, a
 *    run line) and whatever its value;
 *  - a Settings field's default in backend/app/config.py, written `NAME: int = <digits>` or `NAME: bool = True` (or
 *    `False`) at the start of a line, after its indentation: declared once, or the read throws, so a field renamed,
 *    moved or declared twice cannot leave a gate reading nothing or the wrong declaration.
 *
 * What it cannot read: a value set on the Cloud Run service or a job outside the repository (a console edit, a gcloud
 * command run by hand), which no file here records; an env file a deploy names (`--env-vars-file`, none today); an
 * image's own ENV (backend/Dockerfile); a name a workflow builds from parts, or a map it takes whole from a variable
 * or a secret (`${{ vars.… }}`), which no line holds; and a value Settings computes after the declaration (in
 * `__init__` or a validator). A default declared any other way (`Field(default=…)`, an `Annotated` type) reads as no
 * declaration, so the read throws. Each line is read whole and alone: a comment that trails code counts with its
 * line, and a line inside a heredoc or a script's string that starts with `#` is skipped as a comment.
 */

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../..')
const CONFIG_PY = path.join(ROOT, 'backend/app/config.py')
const WORKFLOWS = path.join(ROOT, '.github/workflows')

/** A workflow: its file name under .github/workflows and its text. */
export type Workflow = readonly [file: string, text: string]

/** An executable line of a workflow: its file, its 1-based number and its text as written. */
export interface WorkflowLine {
  readonly file: string
  readonly number: number
  readonly text: string
}

/** backend/app/config.py's text, where the Settings defaults are declared. */
export const readConfig = (): string => readFileSync(CONFIG_PY, 'utf8')

/** Every workflow under .github/workflows, by file name. */
export const workflowFiles = (): Workflow[] =>
  readdirSync(WORKFLOWS)
    .filter((file) => /\.ya?ml$/.test(file))
    .map((file) => [file, readFileSync(path.join(WORKFLOWS, file), 'utf8')] as const)

/** The executable lines of `workflows` that name `name`, in file order and then line order: a comment line is skipped,
    and any other line that holds the name counts, whole. */
export function executableLines(workflows: readonly Workflow[], name: string): WorkflowLine[] {
  return workflows.flatMap(([file, text]) =>
    text.split('\n').flatMap((line, i) => (line.trimStart().startsWith('#') || !line.includes(name) ? [] : [{ file, number: i + 1, text: line }])),
  )
}

/** How a Settings default is written, for the two types the gates read. */
const DEFAULT_VALUE = { int: '(\\d+)', bool: '(True|False)\\b' } as const

/** The default `config` declares for the Settings field `name` (`NAME: int = 300`, `NAME: bool = False`), as written.
    Throws unless the field's default is declared exactly once. */
export function declaredDefault(config: string, name: string, type: keyof typeof DEFAULT_VALUE): string {
  const defaults = [...config.matchAll(new RegExp(`^\\s*${name}\\s*:\\s*${type}\\s*=\\s*${DEFAULT_VALUE[type]}`, 'gm'))]
  if (defaults.length !== 1) throw new Error(`config.py declares ${name}'s default ${defaults.length} times, not once`)
  return defaults[0][1]
}
