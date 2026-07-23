#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ROOT}/scripts/.env.local"
PIN_FILE="${ROOT}/scripts/pin_versions.env"

# shellcheck disable=SC1090
source "${PIN_FILE}"

if [[ -z "${JMOTIF_JAVA_DIR:-}" ]]; then
  for candidate in "${ROOT}/../SAX" "${ROOT}/../jmotif-java"; do
    if [[ -d "${candidate}" ]]; then
      JMOTIF_JAVA_DIR="${candidate}"
      break
    fi
  done
fi
: "${JMOTIF_JAVA_DIR:?set JMOTIF_JAVA_DIR or clone SAX/jmotif-java next to this repo}"
: "${JMOTIF_R_DIR:=${ROOT}/../jmotif-R}"
: "${SAXPY_DIR:=${ROOT}/../saxpy}"
if [[ -z "${JMOTIF_GI_DIR:-}" ]]; then
  for candidate in "${ROOT}/../GI" "${ROOT}/../jmotif-gi"; do
    if [[ -d "${candidate}" ]]; then
      JMOTIF_GI_DIR="${candidate}"
      break
    fi
  done
fi
: "${JMOTIF_GI_DIR:?set JMOTIF_GI_DIR or clone GI/jmotif-gi next to this repo}"
if [[ -z "${SAX_VSM_DIR:-}" ]]; then
  for candidate in "${ROOT}/../sax-vsm_classic" "${ROOT}/../sax-vsm"; do
    if [[ -d "${candidate}" ]]; then
      SAX_VSM_DIR="${candidate}"
      break
    fi
  done
fi
: "${SAX_VSM_DIR:?set SAX_VSM_DIR or clone sax-vsm_classic next to this repo}"
if [[ -z "${GRAMMARVIZ_DIR:-}" ]]; then
  for candidate in "${ROOT}/../grammarviz2_src" "${ROOT}/../grammarviz2"; do
    if [[ -d "${candidate}" ]]; then
      GRAMMARVIZ_DIR="${candidate}"
      break
    fi
  done
fi
: "${GRAMMARVIZ_DIR:?set GRAMMARVIZ_DIR or clone grammarviz2_src next to this repo}"

log() { printf '==> %s\n' "$*"; }

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "missing required command: $1" >&2
    exit 1
  }
}

log "checking prerequisites"
require_cmd git
require_cmd mvn
require_cmd java
require_cmd R
require_cmd Rscript
if command -v uv >/dev/null 2>&1; then
  PYTHON_BOOTSTRAP="uv"
else
  PYTHON_BOOTSTRAP="venv"
  require_cmd python3
fi

maybe_clone() {
  local url="$1"
  local dir="$2"
  local ref="$3"
  if [[ ! -d "${dir}/.git" ]]; then
    log "cloning ${url} into ${dir}"
    git clone "${url}" "${dir}"
  fi
  log "checking out ${ref} in ${dir}"
  git -C "${dir}" fetch --tags origin
  git -C "${dir}" checkout "${ref}"
  # Only fast-forward when tracking a branch; a pinned SHA leaves a detached
  # HEAD (rev-parse --abbrev-ref == "HEAD") and pulling would defeat the pin.
  local branch
  branch="$(git -C "${dir}" rev-parse --abbrev-ref HEAD)"
  if [[ "${branch}" != "HEAD" ]]; then
    git -C "${dir}" pull --ff-only origin "${branch}" || true
  fi
}

maybe_clone "https://github.com/jMotif/SAX.git" "${JMOTIF_JAVA_DIR}" "${JMOTIF_JAVA_REF:-master}"
maybe_clone "https://github.com/jMotif/GI.git" "${JMOTIF_GI_DIR}" "${JMOTIF_GI_REF:-master}"
maybe_clone "https://github.com/jMotif/sax-vsm_classic.git" "${SAX_VSM_DIR}" "${SAX_VSM_REF:-master}"
maybe_clone "https://github.com/GrammarViz2/grammarviz2_src.git" "${GRAMMARVIZ_DIR}" "${GRAMMARVIZ_REF:-master}"
maybe_clone "https://github.com/jMotif/jmotif-R.git" "${JMOTIF_R_DIR}" "${JMOTIF_R_REF:-master}"
maybe_clone "https://github.com/seninp/saxpy.git" "${SAXPY_DIR}" "${SAXPY_REF:-master}"

log "building jmotif-sax (install to local repo for jmotif-gi)"
mvn -q -f "${JMOTIF_JAVA_DIR}/pom.xml" install -P single -DskipTests
JAVA_JAR="${JMOTIF_JAVA_DIR}/target/jmotif-sax-"*"-jar-with-dependencies.jar"
JAVA_JAR="$(ls -1 ${JAVA_JAR} | tail -n 1)"

log "building jmotif-gi (install to local repo for grammarviz2)"
mvn -q -f "${JMOTIF_GI_DIR}/pom.xml" install -DskipTests
GI_JAR="${JMOTIF_GI_DIR}/target/jmotif-gi-"*".jar"
GI_JAR="$(ls -1 ${GI_JAR} | grep -v 'sources\\|javadoc' | head -n 1)"
GI_CP="$(mvn -q -f "${JMOTIF_GI_DIR}/pom.xml" -Dmdep.outputFile=/dev/stdout dependency:build-classpath)"

log "building sax-vsm"
mvn -q -f "${SAX_VSM_DIR}/pom.xml" package -P single -DskipTests
SAX_VSM_JAR="${SAX_VSM_DIR}/target/sax-vsm-"*"-jar-with-dependencies.jar"
SAX_VSM_JAR="$(ls -1 ${SAX_VSM_JAR} | tail -n 1)"

log "building grammarviz2 (RRA)"
mvn -q -f "${GRAMMARVIZ_DIR}/pom.xml" package -P single -DskipTests
GRAMMARVIZ_JAR="${GRAMMARVIZ_DIR}/target/grammarviz2-"*"-jar-with-dependencies.jar"
GRAMMARVIZ_JAR="$(ls -1 ${GRAMMARVIZ_JAR} | tail -n 1)"

log "compiling Java conformance driver"
mkdir -p "${ROOT}/drivers/java"
javac -cp "${GI_JAR}:${GI_CP}" -d "${ROOT}/drivers/java" "${ROOT}/drivers/java/ConformanceRunner.java"
JAVA_CLASSPATH="${GI_JAR}:${GI_CP}:${ROOT}/drivers/java"

log "compiling SAX-VSM conformance driver"
javac -cp "${SAX_VSM_JAR}" -d "${ROOT}/drivers/java" "${ROOT}/drivers/java/SaxVSMConformanceRunner.java"
JAVA_SAXVSM_CLASSPATH="${SAX_VSM_JAR}:${ROOT}/drivers/java"

log "compiling RRA conformance driver"
javac -cp "${GRAMMARVIZ_JAR}" -d "${ROOT}/drivers/java" "${ROOT}/drivers/java/RRAConformanceRunner.java"
JAVA_RRA_CLASSPATH="${GRAMMARVIZ_JAR}:${ROOT}/drivers/java"

log "compiling RRA vs HOT-SAX benchmark driver (optional; needs GrammarViz with RRAIntervalBuilder)"
JAVA_BENCH_CLASSPATH=""
if javac -cp "${GRAMMARVIZ_JAR}" -d "${ROOT}/drivers/java" "${ROOT}/drivers/java/RRAvsHotsaxBench.java" 2>/dev/null; then
  JAVA_BENCH_CLASSPATH="${GRAMMARVIZ_JAR}:${ROOT}/drivers/java"
else
  log "skipped RRAvsHotsaxBench compile at pinned GrammarViz ref — run ./scripts/bench_rra_hotsax.sh to compile against a newer checkout"
fi

log "installing jmotif-R"
R_LIBS_USER="${ROOT}/.build/r-library"
mkdir -p "${R_LIBS_USER}"
export R_LIBS_USER
log "installing R dependencies into ${R_LIBS_USER}"
Rscript -e '
lib <- Sys.getenv("R_LIBS_USER")
dir.create(lib, showWarnings = FALSE, recursive = TRUE)
pkgs <- c("Rcpp", "jsonlite")
need <- pkgs[!vapply(pkgs, function(p) requireNamespace(p, quietly = TRUE, lib.loc = lib), logical(1))]
if (length(need)) install.packages(need, lib = lib, repos = "https://cloud.r-project.org")
'
R CMD INSTALL -l "${R_LIBS_USER}" "${JMOTIF_R_DIR}"

log "installing saxpy"
if command -v uv >/dev/null 2>&1; then
  (cd "${SAXPY_DIR}" && uv pip install -e . >/dev/null)
  PYTHON_BIN="$(cd "${SAXPY_DIR}" && uv run which python)"
else
  PYTHON_VENV="${ROOT}/.build/python-venv"
  if [[ ! -x "${PYTHON_VENV}/bin/python" ]]; then
    python3 -m venv "${PYTHON_VENV}"
  fi
  "${PYTHON_VENV}/bin/pip" install -q -e "${SAXPY_DIR}"
  PYTHON_BIN="${PYTHON_VENV}/bin/python"
fi

cat >"${ENV_FILE}" <<EOF
JMOTIF_JAVA_DIR=${JMOTIF_JAVA_DIR}
JMOTIF_JAVA_JAR=${JAVA_JAR}
JMOTIF_JAVA_CLASSPATH=${JAVA_CLASSPATH}
JMOTIF_GI_DIR=${JMOTIF_GI_DIR}
JMOTIF_GI_JAR=${GI_JAR}
SAX_VSM_DIR=${SAX_VSM_DIR}
SAX_VSM_JAR=${SAX_VSM_JAR}
JAVA_SAXVSM_CLASSPATH=${JAVA_SAXVSM_CLASSPATH}
GRAMMARVIZ_DIR=${GRAMMARVIZ_DIR}
GRAMMARVIZ_JAR=${GRAMMARVIZ_JAR}
JAVA_RRA_CLASSPATH=${JAVA_RRA_CLASSPATH}
JAVA_BENCH_CLASSPATH=${JAVA_BENCH_CLASSPATH}
JMOTIF_R_DIR=${JMOTIF_R_DIR}
R_LIBS_USER=${R_LIBS_USER}
SAXPY_DIR=${SAXPY_DIR}
PYTHON_BIN=${PYTHON_BIN}
EOF

log "wrote ${ENV_FILE}"
log "bootstrap complete"
