/**
 * A sentence read as clauses and noun phrases, for the gates that read what a sentence says rather than how near two of
 * its words stand (E162). legalTruth.spec.tsx's endpoint family reads each clause's subject, verb group and conditions
 * through it, and its consent and one-use families are to move onto it, so a shape one family reads the others read too
 * (lessons/test-gates-must-be-as-wide-as-their-rule.md). A family keeps its own lexicon (what counts as a login, an
 * endpoint or the whole API) and matches it at the places this reading names (matchAt), not anywhere in the sentence.
 * Under its readings the endpoint family keeps main's blanket for "all" and "every" (#1594's fourth round): a clause
 * where "all" or "every" stands before "endpoints" as main read it fails, login word or not, unless this reading finds
 * the phrase narrowed (a phrase after it that picks some out, in brackets or not, the quantifier taken back) or the
 * clause narrowed by a condition or denied, at main's cost ("All endpoints are documented publicly." fails). Under
 * "each" and "any" it keeps main's recall as a floor (#1594's third round): it reads every noun phrase a clause names,
 * at each quantifier (nounPhraseAt), and every login word in the clause, so a clause that names the endpoints taken
 * whole with a login word fails unless this reading finds why it does not say the claim (a condition that narrows, a
 * denial on its verb or its subject, the login word in another role or in the opposite sense), at the cost of failing a
 * login word the endpoints only handle ("Each endpoint counts failed logins.").
 *
 * Tokens (tokensOf). A word is letters and digits, joined by a hyphen or an apostrophe ("API's", "token-based",
 * "can't") or by a point between digits ("99.9"); any other mark is a token of its own. Each keeps where it stands, so
 * a span's own text can be read (spanText) and a family's lexicon matched at a token (matchAt).
 *
 * Noun phrases (nounPhraseAt). A word that takes the quantifier back ("not every", "almost all"), the quantifier
 * ("all", "every", "each", "any", "no", ...), "of" after it ("each of", "every one of"), the determiners ("the", "our",
 * "these", "such", ...), then the words before the head and the head. Those words run on until a word that cannot stand
 * in a noun phrase: a closed-class word (a preposition, a conjunction, a subordinating or relative word, an auxiliary
 * or a modal, a negation, a listed adverb), a mark, or, after the phrase's first word, a verb the lexicon knows
 * (VERB_FORMS) or an adverb in -ly, but for one after a word read as an adjective ("anonymous requests",
 * "unauthenticated calls": ADJECTIVES) and one an auxiliary, a modal or a negation follows, which is a noun there ("an
 * auth proxy does not", "the access logs are"). The head is the last of them, so "each endpoint's documentation" is
 * headed by "documentation". What follows the head is read with it: a prepositional phrase with its own noun phrase
 * ("in the admin namespace"), a relative clause with its relative word or without it ("that returns account data", "we
 * run", and "we have", whose "have" is its verb where a verb group or a mark follows: relativeVerb), a participle
 * ("returning account data", "listed below") and an aside in commas before the verb group (", which returns JSON,").
 * Each restricts the phrase unless it stands in commas, and an aside restricts it too when it names an exception (",
 * except the health check,"). A phrase read as an adverb ("by default", "without exception": adverbAt) is no
 * prepositional phrase. A pronoun is a phrase of its own.
 *
 * Clauses (readSentence). A semicolon or a colon ends one. A subordinating word opens a condition: "when", "whenever",
 * "if", "while", "once" (before a clause), "unless", "because", "although", "though", "whereas", "since", "until", "so
 * that", "as long as", "as soon as", "provided that", with "only", "even", "not only" or "except" directly before it as
 * its own, and so is a comma before it; "only" before a preposition opens one too ("only for anonymous requests"). A
 * condition after a clause's verb is that clause's; one that opens a clause runs to its comma and conditions every
 * clause after it up to a semicolon or a colon ("When you call it, each endpoint requires a login."), and one in commas
 * between a subject and its verb is its clause's. A conjunction ("and", "but", "or", "nor"; "so" and "yet" after a
 * comma) or a comma followed by a verb group carries the clause's subject on to a clause of its own ("returns JSON and
 * also requires a login"); followed by a noun phrase and a verb group, it opens a clause with a subject of its own
 * ("and the login page is public", "and not every endpoint requires a login"); followed by anything else, it joins two
 * nouns ("authentication and authorization"). A quantified noun phrase with a verb group after it, inside a predicate
 * and outside its conditions, opens a clause too, the clause a verb takes as its object ("We guarantee that each
 * endpoint requires a login."). A clause's subject is read after what introduces it (adverbs, connectives and a
 * prepositional phrase, each with its comma or not, and a purpose, with its comma or, where what would read as a
 * relative clause on its object ends the sentence, without one: "To call any endpoint, you need a token.", "To use any
 * endpoint you must log in."), a gerund that opens it takes its object into it ("Using any endpoint requires a
 * login."), and its predicate starts at its verb group (verbGroupAt: auxiliaries, modals, adverbs, a negation and a
 * catenative's "to" before its verb). A negation directly before "only", "merely", "just", "simply" or "solely" adds to
 * the verb and denies nothing ("not only requires authentication but also returns JSON", "does not merely require a
 * login"), so negates and verbGroupAt read it as no negation.
 *
 * Out of reach: a verb the lexicon lacks reads as a noun after a noun, so a phrase runs on over it, and a noun the
 * lexicon also lists as a verb ends a phrase after another noun unless its own verb group follows ("the access logs
 * record every call" reads as "the access" and a verb); a subject named twice ("each endpoint and each page") reads as
 * its first phrase alone, and a pronoun as no more than itself ("each one"); a negation that governs a clause from
 * outside it ("It is not true that ...") is not read; a fronted phrase is an introduction, never a restriction ("In the
 * admin namespace, each endpoint ..."), and a phrase in brackets is not read as the phrase's, though a clause's
 * predicate starts after one between its subject and its verb group (the endpoint family reads what one holds as it
 * would be without the brackets); a prepositional phrase after a noun is read as that noun's, wherever else it may
 * attach ("every endpoint for each request" names its requests, and a family decides whether such a phrase narrows); a
 * quantifier after its noun ("the endpoints all require a login") is not read; and a fronted condition with no comma
 * runs to the first quantified noun phrase with a verb group after its own verb.
 *
 */

export type Token = { text: string; lower: string; start: number; end: number }

export type Postmodifier = {
  kind: 'preposition' | 'relative' | 'participle' | 'aside'
  start: number
  end: number
  /** Restrictive: it picks some of the head out. An aside in commas restricts only when it names an exception, and a
      phrase that includes ("including the login page") never does. */
  restrictive: boolean
  preposition: string | null
  object: NounPhrase | null
}

export type NounPhrase = {
  start: number
  end: number
  /** A word before the quantifier takes it back: "not every", "almost all". */
  takenBack: boolean
  quantifier: string | null
  /** "of" after the quantifier: "each of", "every one of". */
  partitive: boolean
  determiners: string[]
  premodifiers: Token[]
  head: Token
  postmodifiers: Postmodifier[]
}

export type Condition = {
  /** Its first word: the adverb before the subordinating word, or the word itself. */
  start: number
  /** Where its own words start, after the subordinating word. */
  words: number
  end: number
  /** The subordinating word ("when", "if", "so that"), or the preposition after "only" ("for", "to"). */
  subordinator: string
  adverb: 'only' | 'even' | 'not only' | 'except' | null
  comma: boolean
}

export type Clause = {
  start: number
  end: number
  subject: NounPhrase | null
  /** Where its verb group starts. */
  predicate: number
  /** The clause before carried its subject on to this one ("returns JSON and also requires a login"). */
  carried: boolean
  /** The conjunction or comma that opened it. */
  joinedBy: string | null
  /** A fronted condition (before the subject, or in commas between the subject and its verb), and those after its
      verb. */
  conditions: Condition[]
}

export type Reading = { sentence: string; tokens: Token[]; clauses: Clause[] }

export type VerbGroup = { start: number; verb: number; negated: boolean }

const words = (list: string) => new Set(list.split(/\s+/).filter(Boolean))

const QUANTIFIERS = words('all every each any no none some most many much few several both either neither')
const TAKES_BACK = words('not almost nearly virtually practically hardly barely scarcely')
const DETERMINERS = words('the a an this that these those such our your its their my his her')
const PRONOUNS = words('i you he she it we they me him us them everyone everybody everything someone somebody something anyone anybody anything nobody nothing')
const PREPOSITIONS = words(
  'about above across after against along among around as at before behind below beneath beside besides between beyond by despite during except excluding for from in including inside into like near of off on onto outside over past per regarding through throughout to toward towards under unlike upon via with within without',
)
const CONJUNCTIONS = words('and but or nor')
const SUBORDINATORS = words('because although though whereas while unless if when whenever once since until')
const SUBORDINATOR_PHRASES = [['so', 'that'], ['as', 'long', 'as'], ['as', 'soon', 'as'], ['provided', 'that']]
const RELATIVES = words('that which who whom whose where')
const AUXILIARIES = words('am is are was were be been being has have had having do does did can could may might must shall should will would')
const NEGATIONS = words('not never')
/** The words after a negation that turn it into an addition: "not only requires a login but also logs the request",
    "does not merely require a login". */
const ADDITIVE = words('only merely just simply solely')
const ADVERBS = words(
  'also always still only just even then now today currently already again likewise similarly too ever all both each often usually sometimes here there however therefore thus moreover furthermore additionally instead otherwise indeed meanwhile yet so',
)
/** Phrases read as adverbs (adverbAt): "Each endpoint by default requires a login." */
const ADVERBIAL_PHRASES = [['by', 'default'], ['without', 'exception'], ['in', 'practice'], ['at', 'present'], ['at', 'all', 'times'], ['in', 'general'], ['as', 'a', 'rule'], ['of', 'course'], ['for', 'now'], ['in', 'fact'], ['by', 'design'], ['in', 'turn']]
/** A verb that takes another through "to" ("is designed to require", "has to log in"): the verb group reads on past both. */
const CATENATIVES = words('designed built configured meant made going guaranteed bound certain sure able seem seems seemed appear appears appeared continue continues continued tend tends tended has have had need needs ought used')
/** An aside that names an exception restricts what it follows. */
const EXCEPTIONS = words('except excluding but save besides')
/** Words the reading knows as adjectives: the word after one stands in its noun phrase even where the lexicon knows it
    as a verb ("anonymous requests", "unauthenticated calls"). */
const ADJECTIVES = words('anonymous unauthenticated authenticated unauthorized unauthorised authorized authorised signed-in logged-in signed-out logged-out valid invalid expired optional public private incoming')
/** "once" before these is an adverb ("once a day", "works once and"), not a subordinating word. */
const ONCE_AS_ADVERB = words('a an per every each more again and or nor but only daily')
const CONDITION_ADVERBS = words('only even except')
const CLOSED = new Set([...QUANTIFIERS, ...TAKES_BACK, ...DETERMINERS, ...PRONOUNS, ...PREPOSITIONS, ...CONJUNCTIONS, ...SUBORDINATORS, ...RELATIVES, ...AUXILIARIES, ...NEGATIONS, ...ADVERBS])

/** The verbs the reading knows, as lemmas: each is read in its forms (VERB_FORMS). */
const LEMMAS = `accept access add allow answer appear apply approve ask assign audit authenticate authorise authorize become
belong block break bring build cache calculate call cancel cap capture carry cause change charge check choose claim clear close
collect come compare compute confirm connect contain continue control copy cost count cover create cut decide decline decrypt
define delete deliver demand deny depend deploy describe detect differ display document download drop email emit enable
encrypt end enforce ensure enter erase expect expire explain export expose fail fall fetch fill filter find finish fit fix
follow force forget forward front gate generate get give go grant guarantee guard handle happen hash have help hide hit hold
honor honour host identify ignore import include insist invite invoke involve issue join keep know lack last launch lead
leave let lie limit link list live load lock log look lose make manage mandate mark match matter mean measure meet mention
monitor move need notify occur offer open outline own pass pay perform permit pick place plan poll prevent process produce
promise protect prove provide proxy publish pull purchase push put query raise reach read receive recognise recognize
recommend record redirect reduce refer refresh refuse register reject rely remain remember remove renew repeat replace reply
report represent request require reset resolve respond restore restrict retain return reveal review revoke rotate route run
save say scan search secure see seem select sell send serve set share ship show sign sit sort specify start stay stand stop
store stream submit suggest summarise summarize supply support suspend switch take talk tell test throttle track treat
trigger try turn understand unlock update upload use validate vary verify view wait want warn watch work wrap write`
/** Lemmas whose last consonant doubles before -ed and -ing. */
const DOUBLED = words('log cap plan ship stop drop permit submit control')
/** Past forms the rules below do not make. */
const IRREGULAR_PAST = words('had did done took taken sat stood kept sent held wrote written ran got gotten gave given went gone came became saw seen knew known told said led sold found left paid built chose chosen forgot forgotten hid hidden lost meant met made broke broken shown spent brought fell understood lay lain')
const IRREGULAR_OTHER = words('has does doing goes setting getting letting putting running hitting cutting sitting forgetting')

const VERB_FORMS = new Set<string>(IRREGULAR_OTHER)
const PAST_FORMS = new Set<string>(IRREGULAR_PAST)
for (const lemma of words(LEMMAS)) {
  const y = /[^aeiou]y$/.test(lemma)
  const e = lemma.endsWith('e')
  const doubled = DOUBLED.has(lemma) ? lemma + lemma.slice(-1) : null
  const third = y ? `${lemma.slice(0, -1)}ies` : /(?:s|x|z|ch|sh)$/.test(lemma) ? `${lemma}es` : `${lemma}s`
  const past = doubled ? `${doubled}ed` : y ? `${lemma.slice(0, -1)}ied` : e ? `${lemma}d` : `${lemma}ed`
  const ing = doubled ? `${doubled}ing` : lemma.endsWith('ie') ? `${lemma.slice(0, -2)}ying` : e && !lemma.endsWith('ee') ? `${lemma.slice(0, -1)}ing` : `${lemma}ing`
  for (const form of [lemma, third, past, ing]) VERB_FORMS.add(form)
  PAST_FORMS.add(past)
}
for (const form of IRREGULAR_PAST) VERB_FORMS.add(form)

const TOKEN = /[\p{L}\p{N}_]+(?:(?:['’-]|\.(?=\d))[\p{L}\p{N}_]+)*|\S/gu

/** A sentence's words and marks, each with where it stands; a word is read lower-cased, its curly apostrophe straight. */
export const tokensOf = (sentence: string): Token[] =>
  [...sentence.matchAll(TOKEN)].map((m) => ({ text: m[0], lower: m[0].toLowerCase().replace(/’/g, "'"), start: m.index ?? 0, end: (m.index ?? 0) + m[0].length }))

const lower = (token: Token | undefined) => token?.lower ?? ''
const isWord = (token: Token | undefined) => !!token && /^[\p{L}\p{N}_]/u.test(token.text)
const isAdverb = (token: Token | undefined) => !!token && (ADVERBS.has(token.lower) || (/^[a-z]{3,}ly$/.test(token.lower) && !VERB_FORMS.has(token.lower)))
/** How many tokens an adverb or an adverbial phrase ("by default", "without exception") at a token takes: 0 where none
    stands there. A phrase of these is read where an adverb is, never as a prepositional phrase after a noun. */
const adverbAt = (tokens: Token[], at: number) =>
  ADVERBIAL_PHRASES.find((phrase) => phrase.every((w, k) => lower(tokens[at + k]) === w))?.length ?? (isAdverb(tokens[at]) ? 1 : 0)
/** A negation's form: "not", "never", "no longer" and a negated auxiliary or modal ("cannot", "doesn't", "won't"). */
const negationForm = (token: Token | undefined, next?: Token) =>
  !!token && (NEGATIONS.has(token.lower) || /^(?:cannot|[a-z]+n't)$/.test(token.lower) || (token.lower === 'no' && lower(next) === 'longer'))
/** A negation directly before ADDITIVE adds to what follows and denies no verb (#1594's review, Codex's thread
    4367778501): "not only X but also Y" says X. */
const additive = (token: Token | undefined, next?: Token) => negationForm(token, next) && ADDITIVE.has(lower(next))
/** A negation that denies what follows: a negation's form, not before ADDITIVE ("does not require", "never requires";
    "does not merely require" is no denial). */
export const negates = (token: Token | undefined, next?: Token) => negationForm(token, next) && !ADDITIVE.has(lower(next))

/** A word that may stand in a noun phrase: as its first word anything but a closed-class word; after it, not a verb the
    lexicon knows or an adverb either. */
const nominal = (token: Token | undefined, first: boolean) =>
  isWord(token) && !CLOSED.has(lower(token)) && !negates(token) && (first || (!VERB_FORMS.has(lower(token)) && !isAdverb(token)))

/** Whether a verb group starts at a token: adverbs and an additive negation ("not only"), then an auxiliary, a modal, a
    negation or a verb the lexicon knows. A word that takes a quantifier back opens a noun phrase there, not a verb
    group ("and not every endpoint ..."). */
function startsPredicate(tokens: Token[], at: number): boolean {
  if (TAKES_BACK.has(lower(tokens[at])) && QUANTIFIERS.has(lower(tokens[at + 1]))) return false
  let i = at
  for (let n = additive(tokens[i], tokens[i + 1]) ? 1 : adverbAt(tokens, i); n; n = additive(tokens[i], tokens[i + 1]) ? 1 : adverbAt(tokens, i)) i += n
  const word = lower(tokens[i])
  return AUXILIARIES.has(word) || negates(tokens[i], tokens[i + 1]) || VERB_FORMS.has(word)
}

/** A verb group: auxiliaries, modals, adverbs, a negation and a catenative with its "to", then the verb. An additive
    negation ("not only", "does not merely") is read past and leaves the group undenied. */
export function verbGroupAt(tokens: Token[], at: number): VerbGroup {
  let i = at
  let negated = false
  for (;;) {
    const token = tokens[i]
    if (!token) break
    if (additive(token, tokens[i + 1])) i++
    else if (negates(token, tokens[i + 1])) {
      negated = true
      i += token.lower === 'no' ? 2 : 1
    } else if (CATENATIVES.has(token.lower) && lower(tokens[i + 1]) === 'to') i += 2
    else if (AUXILIARIES.has(token.lower)) i++
    else if (adverbAt(tokens, i)) i += adverbAt(tokens, i)
    else break
  }
  return { start: at, verb: i, negated }
}

/** A participle after a head: an -ing word, or a past form with a preposition, an adverb or a verb group after it
    ("listed below", "required by the app", "listed requires"); a past form before an object is the clause's verb. */
const participle = (tokens: Token[], at: number) => {
  const token = tokens[at]
  if (!isWord(token) || CLOSED.has(lower(token))) return false
  if (token.lower.length > 4 && token.lower.endsWith('ing')) return true
  return PAST_FORMS.has(token.lower) && (PREPOSITIONS.has(lower(tokens[at + 1])) || isAdverb(tokens[at + 1]) || startsPredicate(tokens, at + 1))
}

const isMark = (token: Token | undefined) => !!token && !isWord(token)

/** The forms of "have" that may be a relative clause's own verb ("every endpoint we have"). */
const HAVE = words('have has had')
/** A relative clause's verb (#1594's fifth round): its verb group's own, but for an auxiliary that a mark follows, or a
    form of "have" that another verb group follows whose first word is no past form or "been", which is the verb itself
    ("every endpoint we have.", "every endpoint we have requires a login", "all endpoints we have are protected"), so
    the clause it stands in keeps its own verb; "every endpoint we have added this year" keeps "added". */
function relativeVerb(tokens: Token[], at: number): number {
  const group = verbGroupAt(tokens, at)
  for (let k = at; k < group.verb; k++) {
    if (!AUXILIARIES.has(lower(tokens[k]))) continue
    let next = k + 1
    while (next < group.verb && (negates(tokens[next], tokens[next + 1]) || adverbAt(tokens, next))) next += adverbAt(tokens, next) || 1
    const word = lower(tokens[next])
    if (!tokens[next] || isMark(tokens[next])) return k
    if (HAVE.has(lower(tokens[k])) && startsPredicate(tokens, next) && !PAST_FORMS.has(word) && word !== 'been') return k
  }
  return group.verb
}

/** Where a relative clause or a participle ends, read from the word after its relative word, its participle or, for a
    relative clause without its relative word, its own subject: a relative clause's subject and verb group ("that we
    expose", "that returns", "we expose"; relativeVerb), then what follows them, up to the next verb group (its
    clause's), a mark or a conjunction. */
function relativeEnd(tokens: Token[], from: number, clause: boolean): number {
  let i = from
  if (clause) {
    if (!startsPredicate(tokens, i)) i = nounPhraseAt(tokens, i)?.end ?? i
    i = relativeVerb(tokens, i) + 1
  }
  while (i < tokens.length && !startsPredicate(tokens, i) && !isMark(tokens[i]) && !CONJUNCTIONS.has(tokens[i].lower)) i = nounPhraseAt(tokens, i)?.end ?? i + 1
  return Math.min(i, tokens.length)
}

/** A relative clause without its relative word, read as one: a pronoun or a determined noun phrase with a verb group
    after it, straight after the head ("every endpoint we run", "any endpoint the API serves"). */
const reducedRelative = (tokens: Token[], at: number) => {
  if (!PRONOUNS.has(lower(tokens[at])) && !DETERMINERS.has(lower(tokens[at]))) return false
  const subject = nounPhraseAt(tokens, at)
  return !!subject && startsPredicate(tokens, subject.end)
}

/** The closing comma of an aside that opens at a comma and runs to a verb group: -1 where the comma opens a condition,
    a conjunction or anything that does not close before a verb group (a list, another clause). */
function asideEnd(tokens: Token[], comma: number): number {
  if (conditionAt(tokens, comma) || CONJUNCTIONS.has(lower(tokens[comma + 1]))) return -1
  for (let i = comma + 1; i < tokens.length; i++) {
    if (tokens[i].text === ',') return startsPredicate(tokens, i + 1) ? i : -1
    if (/^[.;:!?]$/.test(tokens[i].text)) return -1
  }
  return -1
}

/** What follows a noun phrase's head and belongs to it, each restrictive or not (see the header). */
function readPostmodifiers(tokens: Token[], phrase: NounPhrase): NounPhrase {
  let i = phrase.end
  for (;;) {
    const token = tokens[i]
    if (!token) break
    if (token.text === ',') {
      const close = asideEnd(tokens, i)
      if (close < 0) break
      const exception = EXCEPTIONS.has(lower(tokens[i + 1])) || (lower(tokens[i + 1]) === 'other' && lower(tokens[i + 2]) === 'than')
      phrase.postmodifiers.push({ kind: 'aside', start: i, end: close + 1, restrictive: exception, preposition: null, object: null })
      i = close + 1
    } else if (PREPOSITIONS.has(token.lower) && !adverbAt(tokens, i)) {
      const object = nounPhraseAt(tokens, i + 1)
      const end = object?.end ?? i + 1
      phrase.postmodifiers.push({ kind: 'preposition', start: i, end, restrictive: token.lower !== 'including', preposition: token.lower, object })
      i = end
    } else if (RELATIVES.has(token.lower) || participle(tokens, i)) {
      const end = relativeEnd(tokens, i + 1, RELATIVES.has(token.lower))
      phrase.postmodifiers.push({ kind: RELATIVES.has(token.lower) ? 'relative' : 'participle', start: i, end, restrictive: true, preposition: null, object: null })
      i = end
    } else if (reducedRelative(tokens, i)) {
      const end = relativeEnd(tokens, i, true)
      phrase.postmodifiers.push({ kind: 'relative', start: i, end, restrictive: true, preposition: null, object: null })
      i = end
    } else break
  }
  phrase.end = i
  return phrase
}

/** A word the lexicon knows as a verb that is a noun here, its own verb group after it: an auxiliary, a modal or a
    negation ("an auth proxy does not", "the access logs are"). */
const nounBeforeItsVerb = (tokens: Token[], at: number) => VERB_FORMS.has(lower(tokens[at])) && (AUXILIARIES.has(lower(tokens[at + 1])) || negates(tokens[at + 1], tokens[at + 2]))

/** The noun phrase that starts at a token, with what follows its head (see the header), or null where none does. */
export function nounPhraseAt(tokens: Token[], at: number): NounPhrase | null {
  let i = at
  const word = (k: number) => lower(tokens[k])
  const takenBack = TAKES_BACK.has(word(i)) && QUANTIFIERS.has(word(i + 1))
  if (takenBack) i++
  let quantifier: string | null = null
  let partitive = false
  if (QUANTIFIERS.has(word(i))) {
    quantifier = word(i++)
    if (word(i) === 'one' && word(i + 1) === 'of') i += 2
    else if (word(i) === 'of') i++
    partitive = i > at + (takenBack ? 2 : 1)
  }
  const determiners: string[] = []
  while (DETERMINERS.has(word(i))) determiners.push(word(i++))
  let head: Token
  const premodifiers: Token[] = []
  if (PRONOUNS.has(word(i)) && !determiners.length) head = tokens[i++]
  else {
    const open = () => premodifiers.length === 0 || ADJECTIVES.has(lower(premodifiers[premodifiers.length - 1])) || nounBeforeItsVerb(tokens, i)
    while (nominal(tokens[i], open())) premodifiers.push(tokens[i++])
    const last = premodifiers.pop()
    if (!last) return null
    head = last
  }
  return readPostmodifiers(tokens, { start: at, end: i, takenBack, quantifier, partitive, determiners, premodifiers, head, postmodifiers: [] })
}

/** A condition's opening words at a token: a comma, an adverb ("only", "even", "not only", "except") and the
    subordinating word, or "only" and a preposition. */
function conditionAt(tokens: Token[], at: number): Omit<Condition, 'end'> | null {
  let i = at
  const comma = tokens[i]?.text === ','
  if (comma) i++
  const start = i
  let adverb: Condition['adverb'] = null
  if (lower(tokens[i]) === 'not' && lower(tokens[i + 1]) === 'only') {
    adverb = 'not only'
    i += 2
  } else if (CONDITION_ADVERBS.has(lower(tokens[i]))) adverb = lower(tokens[i++]) as Condition['adverb']
  const phrase = SUBORDINATOR_PHRASES.find((p) => p.every((w, k) => lower(tokens[i + k]) === w))
  if (phrase) return { start, words: i + phrase.length, subordinator: phrase.join(' '), adverb, comma }
  const word = lower(tokens[i])
  if (SUBORDINATORS.has(word) && (word !== 'once' || (isWord(tokens[i + 1]) && !ONCE_AS_ADVERB.has(lower(tokens[i + 1])))))
    return { start, words: i + 1, subordinator: word, adverb, comma }
  if (adverb === 'only' && PREPOSITIONS.has(word)) return { start, words: i + 1, subordinator: word, adverb, comma }
  return null
}

const opensQuantified = (tokens: Token[], at: number) =>
  QUANTIFIERS.has(lower(tokens[at])) || (TAKES_BACK.has(lower(tokens[at])) && QUANTIFIERS.has(lower(tokens[at + 1])))

/** A quantified noun phrase with a verb group after it, starting at a token. */
const quantifiedClauseAt = (tokens: Token[], at: number) => {
  const phrase = opensQuantified(tokens, at) ? nounPhraseAt(tokens, at) : null
  return !!phrase && startsPredicate(tokens, phrase.end)
}

/** Where a fronted condition ends: at its comma, or, with none before the clause ends, at the first quantified noun
    phrase with a verb group after the condition's own verb. */
function frontedEnd(tokens: Token[], from: number): number {
  let i = from
  while (i < tokens.length && !/^[,;:]$/.test(tokens[i].text)) i++
  if (tokens[i]?.text === ',') return i
  let seenVerb = false
  for (let k = from; k < i; k++) {
    if (seenVerb && quantifiedClauseAt(tokens, k)) return k
    seenVerb ||= startsPredicate(tokens, k)
  }
  return i
}

/** Where a purpose before a clause ends ("To call any endpoint, you need a token."): past its comma, when a noun phrase
    and a verb group follow it, or, with no comma, where a relative clause without its relative word would end the
    sentence after the purpose's object, which is the clause itself ("To use any endpoint you must log in."); -1 where
    none does. */
function purposeEnd(tokens: Token[], at: number): number {
  if (lower(tokens[at]) !== 'to' || !VERB_FORMS.has(lower(tokens[at + 1]))) return -1
  for (let i = at + 2; i < tokens.length && !HARD.test(tokens[i].text); i++) {
    if (tokens[i].text !== ',') continue
    const subject = nounPhraseAt(tokens, i + 1)
    return subject && startsPredicate(tokens, subject.end) ? i + 1 : -1
  }
  const object = nounPhraseAt(tokens, at + 2)
  const last = object?.postmodifiers[object.postmodifiers.length - 1]
  return last && last.kind === 'relative' && !RELATIVES.has(lower(tokens[last.start])) && (last.end >= tokens.length || isMark(tokens[last.end])) ? last.start : -1
}

/** Past what introduces a clause's subject: commas, adverbs and connectives, a prepositional phrase, and a purpose with
    its comma. */
function skipIntroduction(tokens: Token[], at: number): number {
  let i = at
  for (;;) {
    const token = tokens[i]
    if (!token || opensQuantified(tokens, i)) return i
    if (token.text === ',' || CONJUNCTIONS.has(token.lower)) i++
    else if (adverbAt(tokens, i)) i += adverbAt(tokens, i)
    else if (purposeEnd(tokens, i) > 0) i = purposeEnd(tokens, i)
    else if (PREPOSITIONS.has(token.lower) && token.lower !== 'to' && nounPhraseAt(tokens, i + 1)) i = nounPhraseAt(tokens, i + 1)?.end ?? i + 1
    else return i
  }
}

const HARD = /^[;:]$/

/** The token that closes a bracket opened at a token, nested brackets read whole; -1 where none closes it. */
export function closingBracket(tokens: Token[], open: number): number {
  let depth = 0
  for (let k = open; k < tokens.length; k++) {
    if (tokens[k].text === '(') depth++
    else if (tokens[k].text === ')' && --depth === 0) return k
  }
  return -1
}

/** A conjunction or a comma that may join two clauses, and where what it joins starts. */
function joinAt(tokens: Token[], at: number): { word: string; after: number } | null {
  const word = lower(tokens[at])
  if (CONJUNCTIONS.has(word)) return { word, after: at + 1 }
  if (tokens[at]?.text !== ',') return null
  const next = lower(tokens[at + 1])
  return CONJUNCTIONS.has(next) || next === 'so' || next === 'yet' ? { word: next, after: at + 2 } : { word: ',', after: at + 1 }
}

type Next = { at: number; carried: boolean; joinedBy: string | null }

/** One clause from a token, with where the next starts (see the header). */
function readClause(tokens: Token[], at: number, how: Next, carriedSubject: NounPhrase | null, fronted: Condition[]): { clause: Clause; fronted: Condition[]; next: Next | null } {
  const conditions = [...fronted]
  let i = at
  let subject = how.carried ? carriedSubject : null
  if (!how.carried) {
    for (let opener = conditionAt(tokens, i); opener; opener = conditionAt(tokens, i)) {
      const end = frontedEnd(tokens, opener.words)
      const condition = { ...opener, end }
      conditions.push(condition)
      fronted = [...fronted, condition]
      i = tokens[end]?.text === ',' ? end + 1 : end
    }
    i = skipIntroduction(tokens, i)
    subject = nounPhraseAt(tokens, i)
    i = subject?.end ?? i
    // A gerund opening the clause takes its object into the subject ("Using any endpoint requires a login.").
    const gerund = subject && !subject.quantifier && !subject.determiners.length && !subject.premodifiers.length && !subject.postmodifiers.length && /ing$/.test(subject.head.lower) && VERB_FORMS.has(subject.head.lower) && !startsPredicate(tokens, i) ? nounPhraseAt(tokens, i) : null
    if (subject && gerund && startsPredicate(tokens, gerund.end)) {
      subject.end = gerund.end
      i = gerund.end
    }
    // A phrase in brackets between the subject and its verb group is passed over, so the predicate starts at the verb
    // group after it ("Every endpoint (in the admin namespace) requires a login."; #1594's fifth round).
    const bracket = subject && tokens[i]?.text === '(' ? closingBracket(tokens, i) : -1
    if (bracket > 0 && startsPredicate(tokens, bracket + 1)) i = bracket + 1
    const between = subject && tokens[i]?.text === ',' ? conditionAt(tokens, i) : null
    if (between) {
      let close = between.words
      while (close < tokens.length && tokens[close].text !== ',' && !HARD.test(tokens[close].text)) close++
      if (tokens[close]?.text === ',' && startsPredicate(tokens, close + 1)) {
        conditions.push({ ...between, end: close })
        i = close + 1
      }
    }
  }
  const predicate = i
  const trailing: Array<Omit<Condition, 'end'>> = []
  let next: Next | null = null
  let p = i
  while (p < tokens.length && !HARD.test(tokens[p].text)) {
    const opener = conditionAt(tokens, p)
    if (opener) {
      trailing.push(opener)
      p = opener.words
      continue
    }
    const join = joinAt(tokens, p)
    if (join) {
      const q = join.after
      if (conditionAt(tokens, q)) {
        p = q
        continue
      }
      if (startsPredicate(tokens, q)) {
        next = { at: q, carried: true, joinedBy: join.word }
        break
      }
      const phrase = nounPhraseAt(tokens, q)
      if (phrase && startsPredicate(tokens, phrase.end)) {
        next = { at: q, carried: false, joinedBy: join.word }
        break
      }
      p = Math.max(q, p + 1)
      continue
    }
    if (p > predicate && !trailing.length && !PREPOSITIONS.has(lower(tokens[p - 1])) && quantifiedClauseAt(tokens, p)) {
      next = { at: p, carried: false, joinedBy: null }
      break
    }
    p++
  }
  const end = p
  trailing.forEach((opener, k) => conditions.push({ ...opener, end: trailing[k + 1]?.start ?? end }))
  return { clause: { start: at, end, subject, predicate, carried: how.carried, joinedBy: how.joinedBy, conditions }, fronted, next }
}

/** A sentence's clauses (see the header). */
export function readSentence(sentence: string): Reading {
  const tokens = tokensOf(sentence)
  const clauses: Clause[] = []
  let fronted: Condition[] = []
  let how: Next = { at: 0, carried: false, joinedBy: null }
  while (how.at < tokens.length) {
    if (HARD.test(tokens[how.at].text)) {
      fronted = []
      how = { at: how.at + 1, carried: false, joinedBy: null }
      continue
    }
    const read = readClause(tokens, how.at, how, clauses[clauses.length - 1]?.subject ?? null, fronted)
    clauses.push(read.clause)
    fronted = read.fronted
    how = read.next ?? { at: read.clause.end, carried: false, joinedBy: null }
  }
  return { sentence, tokens, clauses }
}

/** A span's own text, from a token to the token before another. */
export const spanText = (reading: Reading, from: number, to: number) =>
  to > from && reading.tokens[from] && reading.tokens[to - 1] ? reading.sentence.slice(reading.tokens[from].start, reading.tokens[to - 1].end) : ''

/** Where a family's form, read at a token on the sentence's own text from there on, ends: the token after the last one
    it covers, or -1 where it does not match there. The form starts with ^. */
export function matchAt(reading: Reading, at: number, form: RegExp): number {
  const token = reading.tokens[at]
  const match = token ? form.exec(reading.sentence.slice(token.start)) : null
  if (!token || !match) return -1
  const end = token.start + match[0].length
  const next = reading.tokens.findIndex((t) => t.start >= end)
  return next < 0 ? reading.tokens.length : next
}
