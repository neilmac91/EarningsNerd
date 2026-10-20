import { readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

/**
 * Gate for the UI route: `DESIGN_SYSTEM.md` §4 read by recipe (CLAUDE.md "Read by task", AGENTS.md §1).
 *
 * A UI change built from existing components and tokens reads §4's rules, the list after its recipe
 * block and only the recipes that "Which sections to read" in
 * `.claude/skills/meta/design-docs-maintenance/SKILL.md` names for it: the shared recipes always, a
 * triggered recipe when the change does what its trigger line says, and every other recipe only as the
 * recipe of a component or surface the change uses or edits. The route copies recipe names out of §4's
 * left column, so a renamed recipe would drop out of it unnoticed, and a new recipe would be read by no
 * change that does not use it, whatever its rules bind (#1348 named both; CLAUDE.md rule 12).
 *
 * Two rules, read from the two files themselves:
 *   1. every name the route lists (shared, triggered, or read only through its component) is a recipe in
 *      §4's left column;
 *   2. every recipe in §4's left column sits in exactly one of the route's three lists, so a new recipe
 *      fails here until its author classifies it, as the skill's last paragraph asks.
 *
 * §4's names come from its one fenced recipe block. A name starts at column 0 and its text at column 17,
 * or at column 18 after a 17-character name ("Analysis evidence"); every other line of the block is blank
 * or indented at least 17 spaces, so a name line with a stray indent fails here instead of hiding a recipe.
 * The route's shared and component-only lists are read from their lead-in phrases to the `;` that ends
 * them; a trigger line names its recipes after its last colon once its parentheses are removed, so prose
 * written after the names (", for the focus hand-off") reads as a name and fails rule 1.
 *
 * Out of reach: whether a classification is right, that is whether a recipe read only through its
 * component has a rule that binds other changes, stays the judgment the skill's upkeep paragraph asks of
 * each recipe edit; so does whether a trigger's condition covers the changes it should. The planted forms
 * below are the parsers' and the checks' fixture (AGENTS.md §4), scored on every run.
 */
const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../..')
const read = (rel: string) => readFileSync(path.join(repoRoot, rel), 'utf8')

const SKILL = '.claude/skills/meta/design-docs-maintenance/SKILL.md'
const ROUTE_HEADING = '## Which sections to read for which UI change'
const SHARED_LEAD = 'the shared recipes, whose rules a change can break without touching their component:'
const OWN_LEAD = 'which is the only way these recipes are read:'
const TRIGGER_LEAD = 'the triggered recipes, for what the change adds or changes:'

const NAME_COLUMN = 17
/** Words of letters and slashes, one space apart: "Card / panel", "Accent text/link", "Analysis KPI". */
const RECIPE_NAME = /^[A-Z][A-Za-z/]*(?: [A-Za-z/]+)*$/

/** The recipe names in §4's left column, in order; throws on a block line that breaks the column format. */
function recipeNames(designSystem: string): string[] {
  const lines = designSystem.split('\n')
  const start = lines.findIndex((line) => line.startsWith('## 4. '))
  const end = lines.findIndex((line, i) => i > start && line.startsWith('## '))
  if (start < 0 || end < 0) throw new Error('DESIGN_SYSTEM.md has no §4 followed by another section')
  const fences = lines.slice(start, end).flatMap((line, i) => (line.startsWith('```') ? [start + i] : []))
  const [open, close] = fences
  if (fences.length !== 2 || open === undefined || close === undefined) {
    throw new Error(`§4 must hold one fenced recipe block; it has ${fences.length} fence lines`)
  }
  const names: string[] = []
  for (const [k, line] of lines.slice(open + 1, close).entries()) {
    if (line.trim() === '' || line.startsWith(' '.repeat(NAME_COLUMN))) continue
    const at = `§4 recipe block line ${k + 1} (${JSON.stringify(line.slice(0, 40))})`
    if (/^\s/.test(line)) {
      throw new Error(`${at} is indented less than ${NAME_COLUMN} spaces: neither a recipe name nor its text`)
    }
    const name =
      line.length <= NAME_COLUMN
        ? line.trimEnd()
        : line[NAME_COLUMN - 1] === ' '
          ? line.slice(0, NAME_COLUMN).trimEnd()
          : line[NAME_COLUMN] === ' '
            ? line.slice(0, NAME_COLUMN)
            : null
    if (name === null || !RECIPE_NAME.test(name)) {
      throw new Error(`${at} does not start with a recipe name in the ${NAME_COLUMN}-column left column`)
    }
    if (name.includes(' and ')) throw new Error(`${at}: the route's lists split on " and ", so no recipe name holds it`)
    names.push(name)
  }
  return names
}

type Route = { shared: string[]; own: string[]; triggered: string[][] }

const squash = (text: string) => text.replace(/\s+/g, ' ').trim()
/** "A, B and C" read as [A, B, C]; recipeNames refuses a name holding " and ", and RECIPE_NAME a comma. */
const listNames = (text: string) => text.split(/, | and /).map((name) => name.trim())

/** A trigger line's recipe names: the text after its last colon, once its parentheses are removed. */
function triggerNames(item: string): string[] {
  let text = squash(item).replace(/[;.]$/, '')
  for (let previous = ''; previous !== text; ) {
    previous = text
    text = text.replace(/\([^()]*\)/g, '')
  }
  if (/[()]/.test(text)) throw new Error(`unbalanced parentheses in the trigger line "${squash(item)}"`)
  const colon = text.lastIndexOf(': ')
  if (colon < 0) throw new Error(`the trigger line "${squash(item)}" names no recipes after a colon`)
  return listNames(text.slice(colon + 2))
}

/** The route's three lists, read from the skill's "Which sections to read" section. */
function readRoute(skill: string): Route {
  const lines = skill.split('\n')
  const start = lines.indexOf(ROUTE_HEADING)
  if (start < 0) throw new Error(`${SKILL} has no "${ROUTE_HEADING}" section`)
  const next = lines.findIndex((line, i) => i > start && line.startsWith('## '))
  const section = lines.slice(start, next < 0 ? lines.length : next)
  const text = squash(section.join('\n'))
  const listAfter = (lead: string): string[] => {
    const at = text.indexOf(lead)
    if (at < 0 || text.includes(lead, at + 1)) throw new Error(`the route must say "${lead}" exactly once`)
    const rest = text.slice(at + lead.length)
    const stop = rest.indexOf(';')
    if (stop < 0) throw new Error(`the list after "${lead}" never ends with a ";"`)
    return listNames(rest.slice(0, stop))
  }
  const lead = section.findIndex((line) => squash(line).endsWith(TRIGGER_LEAD))
  if (lead < 0) throw new Error(`the route must say "${TRIGGER_LEAD}"`)
  const items: string[] = []
  for (const line of section.slice(lead + 1)) {
    if (line.trim() === '') break
    if (/^\s*- /.test(line)) items.push(line.replace(/^\s*- /, ''))
    else if (items.length > 0) items[items.length - 1] += ` ${line.trim()}`
    else throw new Error(`the first line after "${TRIGGER_LEAD}" is not a trigger line`)
  }
  return { shared: listAfter(SHARED_LEAD), own: listAfter(OWN_LEAD), triggered: items.map(triggerNames) }
}

/** What breaks the two rules, one message each, in a fixed order; empty when the route and §4 agree. */
function routeProblems(recipes: string[], route: Route): string[] {
  const problems: string[] = []
  const lists: Array<[string, string[]]> = [
    ['shared', route.shared],
    ['triggered', [...new Set(route.triggered.flat())]],
    ['component-only', route.own],
  ]
  for (const name of recipes.filter((recipe, i) => recipes.indexOf(recipe) !== i)) {
    problems.push(`§4 names the recipe "${name}" twice`)
  }
  for (const [list, names] of lists) {
    for (const name of names.filter((n, i) => names.indexOf(n) !== i)) problems.push(`the ${list} list names "${name}" twice`)
    for (const name of names.filter((n) => !recipes.includes(n))) {
      problems.push(`"${name}" in the ${list} list is not a §4 recipe`)
    }
  }
  for (const recipe of new Set(recipes)) {
    const homes = lists.filter(([, names]) => names.includes(recipe)).map(([list]) => list)
    if (homes.length === 0) problems.push(`the §4 recipe "${recipe}" is in none of the route's lists`)
    if (homes.length > 1) problems.push(`the §4 recipe "${recipe}" is in more than one list: ${homes.join(', ')}`)
  }
  return problems
}

const block = (rows: string[]) =>
  ['## 4. Canonical component patterns', '', 'Rules.', '```', ...rows, '```', '', '## 5. Headings'].join('\n')

/** Each left-column form and what the reader makes of it: the names, or a throw. */
const NAME_FORMS: Array<[string, string, string[] | 'throws']> = [
  ['the usual name, its text at column 17', 'Primary button   <Button>  LIGHT: white label', ['Primary button']],
  ['a 16-character name and one space', 'Accent text/link text-brand-strong dark:text-brand-strong-dark', ['Accent text/link']],
  ['a 17-character name pushes its text to column 18', 'Analysis evidence <SourceValue> the shared source', ['Analysis evidence']],
  ['a name whose text starts on the next line', 'Toast', ['Toast']],
  ['a line of text', `${' '.repeat(NAME_COLUMN)}its text, continued`, []],
  ['a blank line', '', []],
  ['a stray indent would hide a recipe', '  Toast          <Toast> raised by a page', 'throws'],
  ['a tab indent would hide a recipe', '\tToast           <Toast>', 'throws'],
  ['text inside the name column', 'Toast <Toast>    raised by a page', 'throws'],
  ['an 18-character name', 'Analysis evidences <SourceValue> the shared source', 'throws'],
  ['a name the lists would split', 'Tabs and panes    <Tabs>', 'throws'],
]

/** Each trigger-line form and the names the reader takes from it. */
const TRIGGER_FORMS: Array<[string, string, string[]]> = [
  [
    'a list, then a parenthesis',
    'a keyboard shortcut: Source pane, Wording changes and Search field (the filing page binds ⌘K and "/"; company search binds "/");',
    ['Source pane', 'Wording changes', 'Search field'],
  ],
  [
    'a parenthesis before the colon',
    'a menu, dropdown, tooltip or explainer (anything anchored to a control that closes on Escape): Popover;',
    ['Popover'],
  ],
  [
    'a colon inside the closing parenthesis',
    'a scroll box on either axis: Filing reader, Analysis table and Admin pages (a scripted scroll is a motion change: §11 too);',
    ['Filing reader', 'Analysis table', 'Admin pages'],
  ],
  ['the last line, ending in a full stop', 'figure tiles outside /analysis: Analysis KPI.', ['Analysis KPI']],
  [
    'prose after the names reads as a name (rule 1 flags it)',
    'a dismiss (a "Show all"): Source pane and Popover, for the focus hand-off;',
    ['Source pane', 'Popover', 'for the focus hand-off'],
  ],
]

const PLANTED = ['Alpha', 'Beta', 'Gamma', 'Delta']
const CLEAN: Route = { shared: ['Alpha'], own: ['Beta'], triggered: [['Gamma'], ['Gamma', 'Delta']] }

/** Each way the route and §4 can disagree, and the clean look-alike, with the messages each must give. */
const ROUTE_FORMS: Array<[string, string[], Route, string[]]> = [
  ['clean: every recipe classified once, a recipe on two trigger lines', PLANTED, CLEAN, []],
  [
    'a new recipe left unclassified',
    [...PLANTED, 'Epsilon'],
    CLEAN,
    ['the §4 recipe "Epsilon" is in none of the route\'s lists'],
  ],
  [
    'a recipe renamed in §4 only',
    ['Alpha', 'Beta', 'Gamma', 'Delta two'],
    CLEAN,
    ['"Delta" in the triggered list is not a §4 recipe', 'the §4 recipe "Delta two" is in none of the route\'s lists'],
  ],
  [
    'a stale name in the shared list',
    PLANTED,
    { ...CLEAN, shared: ['Alpha', 'Omega'] },
    ['"Omega" in the shared list is not a §4 recipe'],
  ],
  [
    'a recipe in two lists',
    PLANTED,
    { ...CLEAN, shared: ['Alpha', 'Beta'] },
    ['the §4 recipe "Beta" is in more than one list: shared, component-only'],
  ],
  [
    'prose read as a trigger name',
    PLANTED,
    { ...CLEAN, triggered: [['Gamma', 'for the focus hand-off'], ['Delta']] },
    ['"for the focus hand-off" in the triggered list is not a §4 recipe'],
  ],
  [
    'a name twice in one list',
    PLANTED,
    { ...CLEAN, own: ['Beta', 'Beta'] },
    ['the component-only list names "Beta" twice'],
  ],
  [
    'a recipe named twice in §4',
    [...PLANTED, 'Beta'],
    CLEAN,
    ['§4 names the recipe "Beta" twice'],
  ],
]

describe('the UI route readers score their planted forms', () => {
  it.each(NAME_FORMS)('§4 left column: %s', (_, row, expected) => {
    if (expected === 'throws') expect(() => recipeNames(block([row]))).toThrow()
    else expect(recipeNames(block([row]))).toEqual(expected)
  })

  it.each(TRIGGER_FORMS)('trigger line: %s', (_, item, expected) => {
    expect(triggerNames(item)).toEqual(expected)
  })

  it.each(ROUTE_FORMS)('route against §4: %s', (_, recipes, route, expected) => {
    expect(routeProblems(recipes, route)).toEqual(expected)
  })

  it('reads a planted route section, its lists and its trigger lines', () => {
    const skill = [
      ROUTE_HEADING,
      '',
      '  - the shared recipes, whose rules a change can break without touching their component: Alpha',
      '    and Card / panel;',
      '  - the recipe of each existing component or surface the change uses or edits, which is the only',
      '    way these recipes are read: Beta, Accent text/link and Analysis evidence;',
      '  - the triggered recipes, for what the change adds or changes:',
      '    - a menu (one that closes on Escape: any): Gamma;',
      '    - a scroll box: Gamma and',
      '      Delta (a scripted scroll: §11 too).',
      '',
      '  The rest of the section.',
      '',
      '## Another section',
      '',
      '- the shared recipes, whose rules a change can break without touching their component: Omega;',
    ].join('\n')
    expect(readRoute(skill)).toEqual({
      shared: ['Alpha', 'Card / panel'],
      own: ['Beta', 'Accent text/link', 'Analysis evidence'],
      triggered: [['Gamma'], ['Gamma', 'Delta']],
    })
  })
})

describe('the UI route in the design-docs skill and DESIGN_SYSTEM.md §4 agree', () => {
  const recipes = recipeNames(read('frontend/DESIGN_SYSTEM.md'))
  const route = readRoute(read(SKILL))

  it('reads every recipe in §4 and every list of the route (a broken reader cannot pass)', () => {
    expect(recipes.length).toBeGreaterThanOrEqual(40)
    expect(route.shared.length).toBeGreaterThanOrEqual(10)
    expect(route.own.length).toBeGreaterThanOrEqual(5)
    expect(route.triggered.length).toBeGreaterThanOrEqual(10)
  })

  it('lists only §4 recipes, and every §4 recipe in exactly one of its three lists', () => {
    expect(
      routeProblems(recipes, route),
      `Fix "Which sections to read" in ${SKILL}: a renamed recipe is renamed there too, and a new one goes ` +
        'in the shared recipes, a trigger line, or the list read only through its component (its last paragraph says which).',
    ).toEqual([])
  })
})
