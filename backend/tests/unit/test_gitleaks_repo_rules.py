"""The repository's gitleaks rules catch the key shapes this stack holds (rule 12 gate).

gitleaks 8.24.3 has no rule for OpenRouter, Supabase, DeepSeek, Resend or Google OAuth keys, nor for
`whsec_` webhook signing secrets, so a key of those shapes reached CI's secret-scan only through
generic-api-key, which needs a key-like name and `=` or `:` before the value: a bare key on a line
of its own passed. GitHub's secret scanning raised alerts 1 to 4 on four such shapes.
`.gitleaks.toml` adds a rule for each. This test holds the file to three things: it extends the
built-in rules rather than replacing them, it restates the built-in global stopwords that `[extend]`
does not carry over, and each rule finds its provider's shape, named or bare, and passes over
placeholders. It applies each rule as gitleaks 8.24.3 does (detect/detect.go): the regex, its first
non-empty group as the secret, Shannon entropy above the rule's threshold, then the global and the
rule's stopwords. Every vector is built at run time, so this file holds no literal a scanner reads.
"""
import base64
import hashlib
import math
import re
import string
import tomllib
from collections import Counter
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[3]
CONFIG = tomllib.loads((ROOT / ".gitleaks.toml").read_text(encoding="utf-8"))
RULES = {rule["id"]: rule for rule in CONFIG["rules"]}
# Read from gitleaks v8.24.3's config/gitleaks.toml, as are the rule ids the repository rules avoid.
VERIFIED_AGAINST = "8.24.3"
BUILT_IN_STOPWORDS = {string.ascii_lowercase, "014df517-39d1-4453-b7b3-9930c563627c"}
# A rule's `path` and the deprecated singular `[rules.allowlist]`, which 8.24.3 still honours, would each
# silence a rule while every vector below still passed. gitleaks reads keys case-insensitively and lets a
# capitalised spelling (`[Allowlist]`, `Entropy`) override the one this file's checks read, so keys are
# compared exactly as written: every allowed key is lower case, and any other spelling is refused.
TOP_KEYS = {"title", "extend", "allowlist", "rules"}
RULE_KEYS = {"id", "description", "regex", "entropy", "keywords", "allowlists"}
BASE62 = string.ascii_letters + string.digits


def _random(alphabet: str, length: int, seed: str) -> str:
    stream = b"".join(hashlib.sha512(f"{seed}:{i}".encode()).digest() for i in range(1 + length // 64))
    return "".join(alphabet[byte % len(alphabet)] for byte in stream[:length])


def _entropy(value: str) -> float:
    counts = Counter(value)
    return -sum(c / len(value) * math.log2(c / len(value)) for c in counts.values())


def _findings(rule_id: str, text: str) -> list[str]:
    rule = RULES[rule_id]
    if not any(keyword in text.lower() for keyword in rule["keywords"]):
        return []
    stopwords = [word.lower() for word in CONFIG["allowlist"]["stopwords"]]
    stopwords += [word.lower() for allow in rule.get("allowlists", []) for word in allow.get("stopwords", [])]
    allowed = [re.compile(pattern) for allow in rule.get("allowlists", []) for pattern in allow.get("regexes", [])]
    found = []
    for match in re.finditer(rule["regex"], text):
        secret = next((group for group in match.groups() if group), match.group(0))
        if _entropy(secret) <= rule.get("entropy", 0.0):
            continue
        if any(word in secret.lower() for word in stopwords) or any(pattern.search(secret) for pattern in allowed):
            continue
        found.append(secret)
    return found


# One key of each shape the stack holds or held, at its real length and alphabet.
KEYS = {
    "deepseek-api-key": "sk-" + _random("0123456789abcdef", 32, "deepseek"),
    "openrouter-api-key": "sk-or-v1-" + _random("0123456789abcdef", 64, "openrouter"),
    "supabase-secret-key": "sb_secret_" + _random(BASE62 + "_-", 31, "supabase"),
    "webhook-signing-secret": "whsec_" + _random(BASE62, 32, "stripe"),
    "resend-api-key": "re_" + _random(BASE62, 8, "resend-id") + "_" + _random(BASE62, 24, "resend"),
    "google-oauth-client-secret": "GOCSPX-" + _random(BASE62 + "_-", 28, "google"),
}
SVIX_SECRET = "whsec_" + base64.b64encode(hashlib.sha256(b"svix").digest()).decode()


def test_the_file_extends_the_built_in_rules():
    assert CONFIG["extend"] == {"useDefault": True}


def test_the_file_restates_the_built_in_global_stopwords():
    assert set(CONFIG["allowlist"]["stopwords"]) == BUILT_IN_STOPWORDS
    assert set(CONFIG["allowlist"]) <= {"description", "stopwords"}  # no allowlist that could hide a finding


def test_the_file_holds_no_key_that_narrows_a_rule():
    assert set(CONFIG) <= TOP_KEYS, sorted(CONFIG)
    assert set(CONFIG["extend"]) == {"useDefault"}  # the one key gitleaks spells in camel case
    for rule in RULES.values():
        assert set(rule) <= RULE_KEYS, f"{rule['id']}: {sorted(rule)}"


def test_the_restated_built_ins_belong_to_ci_s_pinned_gitleaks():
    # A pin bump must re-read the new release's built-in stopwords and rule ids: [extend] drops the
    # former, and a built-in rule sharing a repository rule's id would merge with it.
    job = yaml.safe_load((ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8"))["jobs"]["secret-scan"]
    assert str(job["env"]["GITLEAKS_VERSION"]) == VERIFIED_AGAINST


def test_a_rule_allowlist_holds_placeholder_stopwords_only():
    # A rule's regexes, paths or commits allowlist could silence it wholesale (`regexes = [".*"]`); a
    # reviewed false positive is pinned by fingerprint in .gitleaksignore instead.
    for rule in RULES.values():
        for allow in rule.get("allowlists", []):
            assert set(allow) <= {"description", "stopwords"}, f"{rule['id']}: {sorted(allow)}"


def test_every_rule_has_a_vector_and_a_lowercase_keyword():
    assert set(RULES) == set(KEYS)
    for rule in RULES.values():
        assert rule["keywords"] and all(keyword == keyword.lower() for keyword in rule["keywords"])
        assert rule["description"]


@pytest.mark.parametrize("rule_id", sorted(KEYS))
@pytest.mark.parametrize("line", ["{key}", "OPENAI_API_KEY={key}", 'secret = "{key}"', "  - {key} # rotated"])
def test_each_rule_finds_its_key_bare_or_named(rule_id, line):
    assert _findings(rule_id, line.format(key=KEYS[rule_id])) == [KEYS[rule_id]]


def test_the_webhook_rule_finds_a_svix_secret_with_its_padding():
    assert _findings("webhook-signing-secret", f"RESEND_WEBHOOK_SECRET={SVIX_SECRET}") == [SVIX_SECRET]


@pytest.mark.parametrize("rule_id, text", [
    ("deepseek-api-key", "OPENAI_API_KEY=sk-your-deepseek-key"),
    ("deepseek-api-key", "sk-" + "0" * 32),
    ("openrouter-api-key", "sk-or-v1-..."),
    ("supabase-secret-key", "SUPABASE_SERVICE_KEY=sb_secret_your_supabase_secret_key_here"),
    ("webhook-signing-secret", "STRIPE_WEBHOOK_SECRET=whsec_..."),
    ("webhook-signing-secret", "STRIPE_WEBHOOK_SECRET=whsec_mock_stripe_webhook_12345"),
    # Alert 3's sequential placeholder, which the built-in stopword passes.
    ("webhook-signing-secret", "whsec_1234567890" + string.ascii_lowercase),  # gitleaks:allow (alert 3's placeholder)
    ("resend-api-key", "RESEND_API_KEY=re_test_1234567890"),
    ("resend-api-key", "def store_" + _random(BASE62, 8, "x") + "_" + _random(BASE62, 20, "y") + "():"),
    ("google-oauth-client-secret", "GOOGLE_CLIENT_SECRET=GOCSPX-your-client-secret"),
])
def test_placeholders_and_lookalikes_pass(rule_id, text):
    assert _findings(rule_id, text) == []


def test_the_leaked_shapes_are_caught_without_a_key_name():
    # Alerts 1 and 2 sat after a key name, which generic-api-key reads; a bare copy reached no rule before.
    for rule_id in ("openrouter-api-key", "supabase-secret-key"):
        assert _findings(rule_id, f"see {KEYS[rule_id]} for the account")
