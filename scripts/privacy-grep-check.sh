#!/usr/bin/env bash
#
# scripts/privacy-grep-check.sh
#
# Enforces philosophy bullet #3: "永不保留原声".
# Searches the codebase for any pattern that could indicate raw audio
# is being persisted to disk, logs, or upstream services.
#
# Run locally before commit, and in CI as a hard gate.
# Exit code 0 = clean, 1 = violation found.
#
# Excludes: third-party deps, test fixtures, this script itself, prompts
# (which legitimately discuss "audio" in privacy-design context).

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

# Patterns that suggest raw audio persistence or upstream leak.
# Each pattern is paired with a short rationale.
PATTERNS=(
  '\.wav\b|writeWav|WavWriter'
  '\.pcm\b|writePcm|PcmFileWriter'
  '\.mp3\b|writeMp3|Mp3Writer'
  '\.aac\b(?!.*\.aar)'
  '\.m4a\b'
  'audio.*\.(write|save|persist|dump)'
  'recordToFile|recordToPath|writeAudioToDisk'
  'FileOutputStream.*audio'
  'fs\.writeFile.*\.(wav|pcm|mp3|m4a)'
)

# Files / dirs to exclude (third-party, generated, doc that legitimately mentions audio).
EXCLUDES=(
  ':(exclude)*/node_modules/**'
  ':(exclude)*/.venv/**'
  ':(exclude)*/build/**'
  ':(exclude)*/dist/**'
  ':(exclude)*/.git/**'
  ':(exclude)*/.gradle/**'
  ':(exclude)*/.cxx/**'
  ':(exclude)docs/**'                 # privacy design docs may reference audio
  ':(exclude)scripts/privacy-grep-check.sh'  # the script itself
  ':(exclude)gateway/api/asr_proxy.py'  # ASR forwarding code legitimately mentions audio in comments
  ':(exclude)gateway/api/error_log.py'  # privacy scrub list mentions "audio" / "pcm"
  ':(exclude)poc/poc-6-foreground-service/**'  # PoC-6 has no audio anyway, but mentions in comments
  ':(exclude)*.md'                    # markdown docs OK
)

violations=0

echo "== Privacy grep check =="
for pat in "${PATTERNS[@]}"; do
  echo "  pattern: $pat"
  # git-grep with extended regex; falls back to plain grep if not in a git repo
  if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    if hits=$(git grep -nE "$pat" -- "${EXCLUDES[@]}" 2>/dev/null); then
      echo "    HITS:"
      echo "$hits" | sed 's/^/      /'
      violations=$((violations + 1))
    fi
  else
    if hits=$(grep -rnE --include='*.kt' --include='*.ts' --include='*.tsx' \
                  --include='*.js' --include='*.jsx' --include='*.py' \
                  --exclude-dir=node_modules --exclude-dir=.venv \
                  --exclude-dir=build --exclude-dir=dist --exclude-dir=.git \
                  --exclude-dir=.gradle \
                  "$pat" . 2>/dev/null); then
      echo "    HITS:"
      echo "$hits" | sed 's/^/      /'
      violations=$((violations + 1))
    fi
  fi
done

if [[ $violations -gt 0 ]]; then
  echo
  echo "FAIL: $violations privacy pattern violation(s) found."
  echo "  This may indicate raw audio is being written to disk."
  echo "  See CLAUDE.md philosophy bullet #3 + product design §8.1."
  echo
  echo "  If a hit is a legitimate false positive, add the file to EXCLUDES"
  echo "  in scripts/privacy-grep-check.sh with a comment explaining why."
  exit 1
fi

echo
echo "PASS: no privacy patterns matched."
echo "  (Reminder: this catches obvious patterns. Code review still needed."
echo "   See gateway/api/asr_proxy.py for the runtime invariant.)"
