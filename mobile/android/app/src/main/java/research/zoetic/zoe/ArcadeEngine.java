package research.zoetic.zoe;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.Locale;
import java.util.Random;

/**
 * Zoe Arcade Core Engine (v0.6.0-beta — 100% Offline, Ad-Free, Accessible for Adults & Kids):
 *   1. GEM Resonance Memory (4-petal harmonic Simon with musical note frequencies)
 *   2. Tic-Tac-Toe vs Zoe (Friendly Kid Mode + Unbeatable Minimax Grandmaster)
 *   3. Kloster A_tau(p) Signal Puzzle (strict threshold metacognition mini-game)
 *   4. 20 Questions & Interactive Story Adventure (offline deck + LLM-ready prompts)
 */
final class ArcadeEngine {
    static final double[] PETAL_FREQS_HZ = {523.25, 659.25, 783.99, 1046.50}; // C5, E5, G5, C6
    static final String[] PETAL_NAMES = {"Cobalt C5", "Emerald E5", "Gold G5", "Ruby C6"};

    private static final int[][] WIN_LINES = {
            {0, 1, 2}, {3, 4, 5}, {6, 7, 8},
            {0, 3, 6}, {1, 4, 7}, {2, 5, 8},
            {0, 4, 8}, {2, 4, 6}
    };

    static final class MysteryItem {
        final String name;
        final String category;
        final boolean living;
        final boolean largerThanBackpack;
        final boolean usesElectricity;
        final String hint1;
        final String hint2;

        MysteryItem(String name, String category, boolean living, boolean largerThanBackpack,
                    boolean usesElectricity, String hint1, String hint2) {
            this.name = name;
            this.category = category;
            this.living = living;
            this.largerThanBackpack = largerThanBackpack;
            this.usesElectricity = usesElectricity;
            this.hint1 = hint1;
            this.hint2 = hint2;
        }
    }

    static final List<MysteryItem> MYSTERY_DECK = Arrays.asList(
            new MysteryItem("Sea Otter", "animal", true, false, false,
                    "It floats on its back in Monterey Bay kelp forests.",
                    "It cracks shells on its tummy using a favorite rock."),
            new MysteryItem("Telescope", "science tool", false, true, false,
                    "It gathers distant starlight to help humans explore space.",
                    "Galileo pointed an early version at Jupiter's moons."),
            new MysteryItem("Compass", "navigation tool", false, false, false,
                    "Its needle quietly aligns with Earth's magnetic field.",
                    "Hikers and sailors use it to find north without batteries."),
            new MysteryItem("Rainbow", "natural phenomenon", false, true, false,
                    "You only see it when sunlight meets falling water droplets.",
                    "Violet bends the most and red bends the least inside its arc."),
            new MysteryItem("Piano", "musical instrument", false, true, false,
                    "It has 88 black and white keys that strike tuned strings.",
                    "You can play both quiet lullabies and booming chords on it."),
            new MysteryItem("Lighthouse", "building", false, true, true,
                    "It stands along rocky coasts to keep ships safe at night.",
                    "A spinning Fresnel lens throws its beam miles across the sea."),
            new MysteryItem("Honeybee", "insect", true, false, false,
                    "It dances in figure-eights to share directions to flowers.",
                    "It helps pollinate orchards and builds hexagonal wax combs."),
            new MysteryItem("Satellite", "spacecraft", false, true, true,
                    "It orbits high above Earth relaying GPS timing and weather maps.",
                    "Solar panels unfold like wings to power its instruments.")
    );

    static final class SignalPuzzle {
        final double[] probs;
        final int targetCount;

        SignalPuzzle(double[] probs, int targetCount) {
            this.probs = probs;
            this.targetCount = targetCount;
        }

        int evaluateCount(double tau) {
            int count = 0;
            for (double p : probs) {
                if (p > tau) {
                    count++;
                }
            }
            return count;
        }
    }

    private ArcadeEngine() {
    }

    // --- 1. GEM Resonance Memory ---

    static List<Integer> nextMemoryRound(List<Integer> current, Random rng) {
        List<Integer> out = current == null ? new ArrayList<>() : new ArrayList<>(current);
        Random r = rng == null ? new Random() : rng;
        out.add(r.nextInt(4));
        return out;
    }

    // --- 2. Tic-Tac-Toe (0=empty, 1=player X, 2=Zoe O) ---

    static int checkWinner(int[] board) {
        if (board == null || board.length != 9) {
            return 0;
        }
        for (int[] line : WIN_LINES) {
            int a = board[line[0]];
            if (a != 0 && a == board[line[1]] && a == board[line[2]]) {
                return a;
            }
        }
        return 0;
    }

    static boolean isBoardFull(int[] board) {
        if (board == null || board.length != 9) {
            return true;
        }
        for (int cell : board) {
            if (cell == 0) {
                return false;
            }
        }
        return true;
    }

    static int chooseZoeMove(int[] board, boolean unbeatable, Random rng) {
        List<Integer> open = new ArrayList<>();
        for (int i = 0; i < 9; i++) {
            if (board[i] == 0) {
                open.add(i);
            }
        }
        if (open.isEmpty()) {
            return -1;
        }
        Random r = rng == null ? new Random() : rng;
        if (!unbeatable && r.nextFloat() < 0.42f) {
            return open.get(r.nextInt(open.size()));
        }
        int bestScore = Integer.MIN_VALUE;
        int bestMove = open.get(0);
        int[] copy = Arrays.copyOf(board, 9);
        for (int idx : open) {
            copy[idx] = 2;
            int score = minimax(copy, 0, false);
            copy[idx] = 0;
            if (score > bestScore) {
                bestScore = score;
                bestMove = idx;
            }
        }
        return bestMove;
    }

    private static int minimax(int[] board, int depth, boolean zoeTurn) {
        int winner = checkWinner(board);
        if (winner == 2) {
            return 10 - depth;
        }
        if (winner == 1) {
            return depth - 10;
        }
        if (isBoardFull(board)) {
            return 0;
        }
        if (zoeTurn) {
            int best = Integer.MIN_VALUE;
            for (int i = 0; i < 9; i++) {
                if (board[i] == 0) {
                    board[i] = 2;
                    best = Math.max(best, minimax(board, depth + 1, false));
                    board[i] = 0;
                }
            }
            return best;
        } else {
            int best = Integer.MAX_VALUE;
            for (int i = 0; i < 9; i++) {
                if (board[i] == 0) {
                    board[i] = 1;
                    best = Math.min(best, minimax(board, depth + 1, true));
                    board[i] = 0;
                }
            }
            return best;
        }
    }

    // --- 3. Kloster A_tau(p) Signal Puzzle ---

    static SignalPuzzle generateSignalPuzzle(Random rng) {
        Random r = rng == null ? new Random() : rng;
        double[] raw = new double[5];
        double sum = 0.0;
        for (int i = 0; i < 5; i++) {
            raw[i] = 0.05 + r.nextDouble() * 0.95;
            sum += raw[i];
        }
        for (int i = 0; i < 5; i++) {
            raw[i] = Math.round((raw[i] / sum) * 100.0) / 100.0;
        }
        int target = 1 + r.nextInt(4); // 1..4 strictly above tau
        return new SignalPuzzle(raw, target);
    }

    // --- 4. 20 Questions Offline Judge ---

    static String answerTwentyQuestions(MysteryItem secret, String question) {
        if (secret == null || question == null || question.trim().isEmpty()) {
            return "Ask a yes/no question, ask for a hint, or guess my secret item!";
        }
        String q = question.toLowerCase(Locale.US).trim();
        if (q.contains(secret.name.toLowerCase(Locale.US))) {
            return "YES! You nailed it — it's a " + secret.name + "! Tap New Secret to play another round.";
        }
        if (q.contains("hint")) {
            return "Hint: " + secret.hint1 + " " + secret.hint2;
        }
        if (q.contains("alive") || q.contains("living") || q.contains("animal") || q.contains("creature") || q.contains("breathe")) {
            return secret.living ? "Yes — it is a living creature (" + secret.category + ")!" : "No — it is not alive.";
        }
        if (q.contains("big") || q.contains("large") || q.contains("bigger") || q.contains("backpack") || q.contains("heavy")) {
            return secret.largerThanBackpack ? "Yes — it is larger than a backpack!" : "No — it's smaller than a backpack (or fits right in your hand).";
        }
        if (q.contains("electric") || q.contains("power") || q.contains("battery") || q.contains("plugged") || q.contains("tech")) {
            return secret.usesElectricity ? "Yes — it uses electricity or solar power." : "No — it doesn't need electricity.";
        }
        if (q.contains("space") || q.contains("sky") || q.contains("star") || q.contains("ocean") || q.contains("water") || q.contains("music")) {
            boolean matches = (secret.hint1 + " " + secret.hint2 + " " + secret.category).toLowerCase(Locale.US)
                    .contains(q.contains("space") ? "space" : q.contains("ocean") || q.contains("water") ? "water" : q.contains("music") ? "music" : "sky");
            return matches ? "Yes! You're getting super warm!" : "Not quite — try asking if it's alive, larger than a backpack, or ask for a hint!";
        }
        return "Good question! Here's a clue to keep you moving: " + secret.hint1;
    }

    static short[] synthesizeChimePcm(double freqHz, int durationMs) {
        int sr = 44_100;
        int samples = (sr * Math.max(60, durationMs)) / 1000;
        short[] pcm = new short[samples];
        for (int i = 0; i < samples; i++) {
            double t = (double) i / sr;
            double env = Math.min(1.0, i / 400.0) * Math.exp(-t * 5.2);
            double wave = 0.65 * Math.sin(2.0 * Math.PI * freqHz * t)
                    + 0.25 * Math.sin(2.0 * Math.PI * (freqHz * 2.0) * t)
                    + 0.10 * Math.sin(2.0 * Math.PI * (freqHz * 3.0) * t);
            pcm[i] = (short) Math.max(-32767, Math.min(32767, wave * env * 22000.0));
        }
        return pcm;
    }
}
