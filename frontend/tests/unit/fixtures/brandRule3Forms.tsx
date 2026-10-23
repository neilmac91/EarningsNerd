/**
 * Planted forms for brandCopyRules.spec.ts rule 3 (the Marked Copy Rule; inside the product the device marks
 * every passage the server located, and nothing else, D-044): one component per form, each marked in the comment
 * before it. `flag` is a form rule 3 must name: one that breaks the rule, or one the gate fails closed on, such as
 * a guard it cannot read (D07). `clean` is a look-alike that must pass. `gap` is a form the rule forbids and the
 * gate leaves to review (its header names it), so it must pass too, until the gate reaches it and the mark flips.
 * The spec reads this file in the same program as the app and scores every form on every run, so a change to the
 * gate that loses a form, or catches a look-alike, fails there. Outside the scan roots: the app scan never reads
 * it, and DEVICE_PLACES does not list it. A new form the rule can take joins it with its mark.
 */
import { EnRef, MarkedCopy, cx } from '@/components/ui'
import BrandEmphasis, { default as RenamedEmphasis } from '@/features/marketing/components/BrandEmphasis'
import * as EmphasisModule from '@/features/marketing/components/BrandEmphasis'
import CitationChip from '@/features/filings/components/copilot/CitationChip'
import CopilotMessage, { type CopilotMessageData } from '@/features/filings/components/copilot/CopilotMessage'
import NarrativePane, { type NarrativeState } from '@/features/analysis/components/NarrativePane'
import type { CopilotCitation } from '@/features/filings/api/copilot-api'
import type { RenderedBlock } from '@/features/summaries/api/summaries-api'
import type { RiskFactor } from '@/types/summary'

const BLOCK = 'en-marked px-3.5 py-2.5 font-editorial text-base leading-relaxed'
const isLocated = (risk: RiskFactor) => risk.source_verified === true

/** D01 flag: a marker on every row, located or not. */
export function D01({ risks }: { risks: RiskFactor[] }) {
  return (
    <MarkedCopy>
      <ul>
        {risks.map((risk, i) => (
          <li key={i}>
            <h3>{risk.summary}<EnRef label={`[${i + 1}]`} /></h3>
          </li>
        ))}
      </ul>
    </MarkedCopy>
  )
}

/** D02 flag: a marker guarded by the row's link, not by the server's located flag. */
export function D02({ risks }: { risks: RiskFactor[] }) {
  return (
    <MarkedCopy>
      <ul>
        {risks.map((risk, i) => (
          <li key={i}>
            <h3>{risk.summary}{risk.source_url && <EnRef label={`[${i + 1}]`} />}</h3>
          </li>
        ))}
      </ul>
    </MarkedCopy>
  )
}

/** D03 flag: a marker on the rows the server did not locate (the guard negated). */
export function D03({ risks }: { risks: RiskFactor[] }) {
  return (
    <MarkedCopy>
      <ul>
        {risks.map((risk, i) => (
          <li key={i}>
            <h3>{risk.summary}{!risk.source_verified && <EnRef label={`[${i + 1}]`} />}</h3>
          </li>
        ))}
      </ul>
    </MarkedCopy>
  )
}

/** D04 flag: `!== false` lets an unknown (null) row through. */
export function D04({ risks }: { risks: RiskFactor[] }) {
  return (
    <MarkedCopy>
      <ul>
        {risks.map((risk, i) => (
          <li key={i}>
            <h3>{risk.summary}{risk.source_verified !== false && <EnRef label={`[${i + 1}]`} />}</h3>
          </li>
        ))}
      </ul>
    </MarkedCopy>
  )
}

/** D05 flag: a marked block on every row, located or not. */
export function D05({ risks }: { risks: RiskFactor[] }) {
  return (
    <ul>
      {risks.map((risk, i) => (
        <li key={i}>
          <blockquote className={cx(BLOCK, 'text-text-primary-light dark:text-text-primary-dark')}>{risk.supporting_evidence}</blockquote>
        </li>
      ))}
    </ul>
  )
}

/** D06 flag: the located test sits on the wrong branch: the marker lands on the rows not located. */
export function D06({ risks }: { risks: RiskFactor[] }) {
  return (
    <MarkedCopy>
      <ul>
        {risks.map((risk, i) => (
          <li key={i}>
            <h3>{risk.summary}{risk.source_verified === true ? null : <EnRef label={`[${i + 1}]`} />}</h3>
          </li>
        ))}
      </ul>
    </MarkedCopy>
  )
}

/** D07 flag: a guard through a helper the gate does not read: it fails closed (test the field, or hold it in a const). */
export function D07({ risks }: { risks: RiskFactor[] }) {
  return (
    <MarkedCopy>
      <ul>
        {risks.map((risk, i) => (
          <li key={i}>
            <h3>{risk.summary}{isLocated(risk) && <EnRef label={`[${i + 1}]`} />}</h3>
          </li>
        ))}
      </ul>
    </MarkedCopy>
  )
}

/** D08 flag: a second marker on one row (the heading's and the excerpt's), whose twins would overprint. */
export function D08({ risks }: { risks: RiskFactor[] }) {
  return (
    <MarkedCopy>
      <ul>
        {risks.map((risk, i) =>
          risk.source_verified === true ? (
            <li key={i}>
              <h3>{risk.summary}<EnRef label={`[${i + 1}]`} /></h3>
              <blockquote className={BLOCK}>{risk.supporting_evidence}<EnRef label={`[${i + 1}a]`} /></blockquote>
            </li>
          ) : null,
        )}
      </ul>
    </MarkedCopy>
  )
}

/** D09 flag: an answer's line with two markers in the margin's copy (Ask's shape): their twins overprint. */
export function D09() {
  return (
    <MarkedCopy>
      <p>
        Total net sales were $416.2B<EnRef label="[1]" /> and Services grew 13.5%<EnRef label="[2]" />.
      </p>
    </MarkedCopy>
  )
}

/** D10 flag: markers mapped into one line. */
export function D10({ citations }: { citations: CopilotCitation[] }) {
  return (
    <MarkedCopy>
      <p>
        Revenue rose.{citations.map((c) => <EnRef key={c.n} label={`[${c.n}]`} />)}
      </p>
    </MarkedCopy>
  )
}

/** D11 flag: a margin beside an Ask answer, which keeps its citation chips. */
export function D11({ message }: { message: CopilotMessageData }) {
  return (
    <MarkedCopy>
      <p>From the filing<EnRef label="[1]" /></p>
      <CopilotMessage message={message} />
    </MarkedCopy>
  )
}

/** D12 flag: a margin beside the Multi-Period narrative, which keeps its citation chips. */
export function D12({ state }: { state: NarrativeState }) {
  return (
    <MarkedCopy>
      <p>From the filing<EnRef label="[1]" /></p>
      <NarrativePane state={state} />
    </MarkedCopy>
  )
}

/** D13 flag: a margin around an answer's citation chips. */
export function D13({ citation }: { citation: CopilotCitation }) {
  return (
    <MarkedCopy>
      <p>Revenue rose<EnRef label="[1]" /> <CitationChip citation={citation} /></p>
    </MarkedCopy>
  )
}

/** D14 flag: a margin without a marker. */
export function D14() {
  return (
    <MarkedCopy>
      <p>A sentence of ours, cited nowhere.</p>
    </MarkedCopy>
  )
}

/** D15 flag: a bare gutter outside MarkedCopy. */
export function D15() {
  return <div className="en-margin" />
}

/** D16 clean: the filing page's rows: the marker and the marked block on the located rows only. */
export function D16({ risks }: { risks: RiskFactor[] }) {
  const located = risks.flatMap((risk, i) => (risk.source_verified === true ? [i] : []))
  const list = (
    <ul>
      {risks.map((risk, i) => {
        const isRowLocated = risk.source_verified === true
        return (
          <li key={i}>
            <h3>{risk.summary}{isRowLocated && <EnRef label={`[${located.indexOf(i) + 1}]`} />}</h3>
            {isRowLocated ? <blockquote className={BLOCK}>{risk.supporting_evidence}</blockquote> : <blockquote>{risk.supporting_evidence}</blockquote>}
          </li>
        )
      })}
    </ul>
  )
  return located.length > 0 ? <MarkedCopy>{list}</MarkedCopy> : list
}

/** D17 clean: the truthy test (the field is `boolean | null`), the block on a ternary. */
export function D17({ risks }: { risks: RiskFactor[] }) {
  return (
    <MarkedCopy>
      <ul>
        {risks.map((risk, i) => (
          <li key={i}>
            <h3>{risk.summary}{risk.source_verified && <EnRef label={`[${i + 1}]`} />}</h3>
            {risk.source_verified !== true ? <blockquote>{risk.supporting_evidence}</blockquote> : <blockquote className={BLOCK}>{risk.supporting_evidence}</blockquote>}
          </li>
        ))}
      </ul>
    </MarkedCopy>
  )
}

/** D18 clean: only the located rows are listed, the filter inside the guard. */
export function D18({ risks }: { risks: RiskFactor[] }) {
  return (
    <MarkedCopy>
      <ul>
        {risks.map((risk, i) =>
          risk.source_verified === true && risk.supporting_evidence ? (
            <li key={i}>
              <h3>{risk.summary}<EnRef label={`[${i + 1}]`} /></h3>
            </li>
          ) : null,
        )}
      </ul>
    </MarkedCopy>
  )
}

/** D19 clean: the landing's one evidence row, located by its picker (pickEvidence) before it renders. */
export function D19({ excerpt }: { excerpt: string }) {
  return (
    <MarkedCopy>
      <div>
        <p>{excerpt.slice(0, 40)}<EnRef label="[1]" /></p>
        <blockquote className={BLOCK}>{excerpt}</blockquote>
      </div>
    </MarkedCopy>
  )
}

/** D20 clean: Ask's chips with no margin, as the product renders them. */
export function D20({ citation }: { citation: CopilotCitation }) {
  return <p>Revenue rose <CitationChip citation={citation} /></p>
}

/** D21 gap: the guard reads the located flag of another row than its own. */
export function D21({ risks }: { risks: RiskFactor[] }) {
  return (
    <MarkedCopy>
      <ul>
        {risks.map((risk, i) => (
          <li key={i}>
            <h3>{risk.summary}{risks[0].source_verified === true && <EnRef label={`[${i + 1}]`} />}</h3>
          </li>
        ))}
      </ul>
    </MarkedCopy>
  )
}

/** D22 clean: the summary's quote blocks: the marked block on a quote whose evidence the server located, the neutral
    hairline on any other, and no marker or twin. */
export function D22({ blocks }: { blocks: RenderedBlock[] }) {
  return (
    <div>
      {blocks.map((block, i) =>
        block.kind === 'quote' && block.evidence?.verified === true ? (
          <blockquote key={i} className={BLOCK}>“{block.text}”</blockquote>
        ) : (
          <blockquote key={i} className="border-l-2 pl-3.5 italic">“{block.text}”</blockquote>
        ),
      )}
    </div>
  )
}

/** D23 flag: a quote the server did not locate takes the marked block. */
export function D23({ blocks }: { blocks: RenderedBlock[] }) {
  return <div>{blocks.map((block, i) => (block.kind === 'quote' ? <blockquote key={i} className={BLOCK}>“{block.text}”</blockquote> : null))}</div>
}

/** D24 flag: a quote block carries a marker: the marker belongs on a row's heading, and a quote has none. */
export function D24({ blocks }: { blocks: RenderedBlock[] }) {
  return (
    <div>
      {blocks.map((block, i) =>
        block.evidence?.verified === true ? (
          <blockquote key={i} className={BLOCK}>“{block.text}”<EnRef label={`[${i + 1}]`} /></blockquote>
        ) : null,
      )}
    </div>
  )
}

/** D26 flag: a quote the server did not locate takes the highlight's tint and hairline. */
export function D26({ blocks }: { blocks: RenderedBlock[] }) {
  return <div>{blocks.map((block, i) => (block.kind === 'quote' ? <blockquote key={i} className="en-mark">“{block.text}”</blockquote> : null))}</div>
}

/** D27 flag: a located quote takes the highlight's tint and hairline (the running-text form) in place of the marked block. */
export function D27({ blocks }: { blocks: RenderedBlock[] }) {
  return (
    <div>
      {blocks.map((block, i) =>
        block.evidence?.verified === true ? (
          <blockquote key={i}>
            <span className="en-mark">“{block.text}”</span>
          </blockquote>
        ) : null,
      )}
    </div>
  )
}

/** D28 clean: the highlight under a phrase of ours, the brand's signature. */
export function D28() {
  return (
    <h1>
      Read the filing faster. Keep <BrandEmphasis>the source</BrandEmphasis> in view.
    </h1>
  )
}

/** D25 flag: a located quote block in a margin, with no marker for a twin to repeat. */
export function D25({ block }: { block: RenderedBlock }) {
  return (
    <MarkedCopy>
      <blockquote className={BLOCK}>“{block.text}”</blockquote>
    </MarkedCopy>
  )
}

/** D29 flag: a marker a same-file helper returns, called in a row: the row reader does not follow a plain call's
    return, so the margin reads as holding no marker and the gate fails closed. */
export function D29({ risks }: { risks: RiskFactor[] }) {
  const marker = (i: number) => <EnRef label={`[${i + 1}]`} />
  return (
    <MarkedCopy>
      <ul>
        {risks.map((risk, i) => (
          <li key={i}>
            <h3>{risk.summary}{marker(i)}</h3>
          </li>
        ))}
      </ul>
    </MarkedCopy>
  )
}

/** D30 gap: a second marker a same-file helper returns, beside the row's own guarded marker: the row reader does not
    follow a plain call's return, so it counts one marker on the row. */
export function D30({ risks }: { risks: RiskFactor[] }) {
  const extra = (i: number) => <EnRef label={`[${i + 1}]`} />
  return (
    <MarkedCopy>
      <ul>
        {risks.map((risk, i) => (
          <li key={i}>
            <h3>
              {risk.summary}
              {risk.source_verified === true && <EnRef label={`[${i + 1}]`} />}
              {extra(i)}
            </h3>
          </li>
        ))}
      </ul>
    </MarkedCopy>
  )
}

/** D31 flag: a new or reverted surface bypasses the shared promotional owner with the old mark. */
export function D31() {
  return <h2>The summary that <span className="en-mark">shows its work</span>.</h2>
}

/** D32 clean: the shared emphasis imported under another name is still the same owner. */
export function D32() {
  return <h2>The summary that <RenamedEmphasis>shows its work</RenamedEmphasis>.</h2>
}

/** D33 flag: an aliased promotional emphasis inside a quote is not a located-passage treatment. */
export function D33() {
  return <blockquote><RenamedEmphasis>Words from the filing</RenamedEmphasis></blockquote>
}

/** D34 clean: an unrelated component parameter named BrandEmphasis is not the imported owner. */
export function D34({ BrandEmphasis }: { BrandEmphasis: (props: { children: string }) => React.ReactNode }) {
  return <blockquote><BrandEmphasis>Words from the filing</BrandEmphasis></blockquote>
}

/** D35 flag: the namespace import is the same owner and cannot highlight a price. */
export function D35() {
  return <EmphasisModule.default>$9 a month</EmphasisModule.default>
}

/** D36 flag: copying only the C5 class still bypasses the owner. */
export function D36() {
  return <h2>Research <span className="en-hero-emphasis">with receipts</span>.</h2>
}

/** D37 flag: self-closing emphasis with a children prop still renders the figure it carries. */
export function D37() {
  // eslint-disable-next-line react/no-children-prop -- planted AST form verifies children-prop content.
  return <RenamedEmphasis children="$9 a month" />
}

/** D38 clean: the namespace import with a text-only children prop is a promotional phrase. */
export function D38() {
  // eslint-disable-next-line react/no-children-prop -- planted AST form verifies namespace children-prop content.
  return <h2>Research <EmphasisModule.default children="with receipts" />.</h2>
}
