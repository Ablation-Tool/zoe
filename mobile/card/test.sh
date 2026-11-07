#!/usr/bin/env bash
set -euo pipefail

ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
: "${JCARD_SIM:?Set JCARD_SIM to a checksum-verified jCardSim 3.0.5.x JAR}"
: "${JUNIT_JAR:?Set JUNIT_JAR to JUnit 4.13.2}"
: "${HAMCREST_JAR:?Set HAMCREST_JAR to Hamcrest 1.3}"
JAVAC=${JAVAC:-javac}
JAVA=${JAVA:-java}
BUILD="$ROOT/build"

rm -rf -- "$BUILD"
mkdir -p "$BUILD/main" "$BUILD/test"
"$JAVAC" -source 8 -target 8 -g -cp "$JCARD_SIM" -d "$BUILD/main" \
  "$ROOT/src/main/java/research/nuclide/zoe/card/ZoeCard.java"
"$JAVAC" -source 8 -target 8 -g -cp "$JCARD_SIM:$JUNIT_JAR:$BUILD/main" -d "$BUILD/test" \
  "$ROOT/src/test/java/research/nuclide/zoe/card/ZoeCardTest.java"
"$JAVA" -cp "$JCARD_SIM:$JUNIT_JAR:$HAMCREST_JAR:$BUILD/main:$BUILD/test" \
  org.junit.runner.JUnitCore research.nuclide.zoe.card.ZoeCardTest
PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s "$ROOT/host" -p 'test_*.py'
PYTHONDONTWRITEBYTECODE=1 python "$ROOT/host/manifest.py" "$ROOT"
wc -c "$ROOT/src/main/java/research/nuclide/zoe/card/ZoeCard.java" \
  "$BUILD/main/research/nuclide/zoe/card/ZoeCard.class"
