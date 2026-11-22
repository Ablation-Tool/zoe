package research.zoetic.zoe;

import android.os.Bundle;
import android.text.InputType;
import android.view.View;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.Spinner;
import android.widget.TextView;

import androidx.activity.ComponentActivity;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.Locale;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public final class ElizaGemActivity extends ComponentActivity {
    private final ExecutorService executor = Executors.newSingleThreadExecutor();
    private final ElizaGemClient client = new ElizaGemClient();
    private final List<String> transcriptLines = new ArrayList<>();
    private ZoeBrainEngine brain;
    private ZoeNativeVoice nativeVoice;
    private ChladniPadView chladniPad;
    private ChladniSynth chladniSynth;
    private TextView chladniInfo;
    private Button chladniModeButton;
    private TextView status;
    private EditText endpointInput;
    private Button gearButton;
    private EditText chatInput;
    private TextView messagesView;
    private EditText relayInput;
    private TextView digestView;
    private TextView phase3View;
    private TextView phase4View;
    private TextView phase5View;
    private LinearLayout labRelayDrawer;
    private Button labRelayToggle;
    private EditText cloudKeyInput;
    private Spinner cloudModelSpinner;
    private TextView cloudKeyBadge;
    private String currentGear = "gear1";

    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        chladniSynth = new ChladniSynth();
        brain = new ZoeBrainEngine(this);
        nativeVoice = new ZoeNativeVoice();

        ScrollView scroll = new ScrollView(this);
        scroll.setBackgroundColor(android.graphics.Color.TRANSPARENT);
        LinearLayout content = Ui.vertical(this);
        content.setBackgroundColor(android.graphics.Color.TRANSPARENT);
        content.setPadding(Ui.dp(this, 16), Ui.dp(this, 12), Ui.dp(this, 16), Ui.dp(this, 24));
        scroll.addView(content);
        setContentView(Ui.wrapWithBackdrop(this, scroll));
        Ui.configureEdgeToEdge(this, content);

        content.addView(Ui.topBar(this, "Eliza-GEM Studio", "Chladni pad · Lab bridge"));

        status = Ui.statusBanner(this, "Studio idle. Play Chladni offline or connect to Lab.", Ui.COBALT);
        status.setId(R.id.eliza_status);
        content.addView(status);

        // 1. Offline Chladni Resonance Pad (works anywhere with zero network)
        content.addView(Ui.section(this, "Chladni Resonance"));
        LinearLayout cymCard = Ui.vertical(this);
        cymCard.setBackground(Ui.cardBackground(this, 22));
        cymCard.setPadding(Ui.dp(this, 16), Ui.dp(this, 14), Ui.dp(this, 16), Ui.dp(this, 14));

        LinearLayout cymHeader = new LinearLayout(this);
        cymHeader.setOrientation(LinearLayout.HORIZONTAL);
        cymHeader.setGravity(android.view.Gravity.CENTER_VERTICAL);
        cymHeader.setBackgroundColor(android.graphics.Color.TRANSPARENT);
        View cymSprout = Ui.gemHomeButton(this, 32, () -> Ui.goHome(this));
        cymHeader.addView(cymSprout, new LinearLayout.LayoutParams(Ui.dp(this, 48), Ui.dp(this, 48)));
        chladniInfo = Ui.text(this, "Square Atelier · Touch plate to sweep harmonics", 13, Ui.GOLD);
        chladniInfo.setPadding(Ui.dp(this, 10), 0, 0, 0);
        cymHeader.addView(chladniInfo, new LinearLayout.LayoutParams(
                0, LinearLayout.LayoutParams.WRAP_CONTENT, 1.0f));
        cymCard.addView(cymHeader);

        chladniPad = new ChladniPadView(this);
        chladniPad.setId(R.id.eliza_chladni_pad);
        chladniPad.setContentDescription("Interactive Chladni eigenmode resonance pad. Drag to sweep harmonics.");
        LinearLayout.LayoutParams padParams = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, Ui.dp(this, 210));
        padParams.setMargins(0, Ui.dp(this, 8), 0, Ui.dp(this, 10));
        cymCard.addView(chladniPad, padParams);

        chladniModeButton = Ui.button(this, "Plate: Square Atelier", Ui.GOLD, view -> {
            chladniPad.toggleModeType();
            updateChladniLabels();
        });
        chladniModeButton.setId(R.id.eliza_chladni_mode);
        Button playChord = Ui.primaryButton(this, "Play Chladni Chord", Ui.CYAN, view -> {
            chladniSynth.play(chladniPad.modeType(), chladniPad.modes(), chladniPad.roseSymmetry());
            status.setText("Playing offline Chladni harmonic chord.");
        });
        playChord.setId(R.id.eliza_chladni_play);
        cymCard.addView(Ui.buttonRow(this, chladniModeButton, playChord));
        Button singZoe = Ui.button(this, "Sing Zoe (Native Voice)", Ui.RUBY, view -> {
            nativeVoice.singZoe(null);
            status.setText("Singing Zoe's native Rosenberg-Klatt soprano theme (44.1 kHz offline).");
        });
        singZoe.setId(R.id.eliza_sing_zoe);
        cymCard.addView(singZoe);
        content.addView(cymCard);

        chladniPad.setModeListener((modeType, modes, roseSymmetry) -> updateChladniLabels());
        updateChladniLabels();

        // 2. Workstation Eliza-GEM Bridge (loopback ADB or remote HTTPS)
        content.addView(Ui.section(this, "Workstation Bridge"));
        content.addView(Ui.text(this, "USB loopback (8765) or HTTPS", 13.5f, Ui.MUTED));

        endpointInput = Ui.input(this, ElizaGemClient.savedEndpoint(this), "http://127.0.0.1:8765 or https://...");
        endpointInput.setId(R.id.eliza_endpoint);
        endpointInput.setSingleLine(true);
        content.addView(endpointInput);

        Button connect = Ui.primaryButton(this, "Connect / Refresh", Ui.CYAN, view -> connectStudio());
        connect.setId(R.id.eliza_connect);
        gearButton = Ui.button(this, "Gear 1 · ELIZA", Ui.PINK, view -> toggleGear());
        gearButton.setId(R.id.eliza_gear);
        content.addView(Ui.buttonRow(this, connect, gearButton));

        LinearLayout composer = new LinearLayout(this);
        composer.setOrientation(LinearLayout.HORIZONTAL);
        chatInput = Ui.input(this, "", "Ask Eliza-GEM or say `relay ...`");
        chatInput.setId(R.id.eliza_input);
        composer.addView(chatInput, new LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1.0f));
        Button send = Ui.button(this, "Send", Ui.CYAN, view -> sendChat());
        send.setId(R.id.eliza_send);
        LinearLayout.LayoutParams sendParams = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.WRAP_CONTENT, LinearLayout.LayoutParams.WRAP_CONTENT);
        sendParams.setMargins(Ui.dp(this, 8), 0, 0, 0);
        composer.addView(send, sendParams);
        content.addView(composer, Ui.margins(
                LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT, this, 4));

        messagesView = Ui.text(this,
                "Offline glass-box instrument (not a Zoe copy).",
                14, Ui.TEXT);
        messagesView.setId(R.id.eliza_messages);
        messagesView.setBackground(Ui.panelBackground(this, Ui.PANEL, Ui.withAlpha(Ui.PINK, 110), 16));
        messagesView.setPadding(Ui.dp(this, 14), Ui.dp(this, 14), Ui.dp(this, 14), Ui.dp(this, 14));
        messagesView.setTextIsSelectable(true);
        content.addView(messagesView);

        // Collapsible Drawer: Lab Relay & Phase 3 Scorecard
        labRelayDrawer = Ui.vertical(this);
        labRelayDrawer.setBackgroundColor(android.graphics.Color.TRANSPARENT);
        labRelayDrawer.setVisibility(View.GONE);

        labRelayDrawer.addView(Ui.section(this, "Closed-Loop Digestion"));
        digestView = Ui.text(this,
                "Privacy Firewall active — SafeConvert, Privacy Vault, raw photos & private chats stay on this phone.\n"
                        + "Tap Feed & Digest Lab to share learned patterns and pull refined priors back.",
                14, Ui.TEXT);
        digestView.setId(R.id.eliza_digest_card);
        digestView.setBackground(Ui.cardBackground(this, 20));
        digestView.setPadding(Ui.dp(this, 16), Ui.dp(this, 14), Ui.dp(this, 16), Ui.dp(this, 14));
        digestView.setTextIsSelectable(true);
        labRelayDrawer.addView(digestView);

        Button digestBtn = Ui.primaryButton(this, "Feed & Digest Lab", Ui.RUBY, view -> digestMobileToLab());
        digestBtn.setId(R.id.eliza_digest_mobile);
        Button syncMem = Ui.button(this, "Sync notes only", Ui.GOLD, view -> syncPhoneMemory());
        syncMem.setId(R.id.eliza_sync_memory);
        labRelayDrawer.addView(Ui.buttonRow(this, digestBtn, syncMem));

        labRelayDrawer.addView(Ui.section(this, "Shared Lab Relay"));
        LinearLayout relayRow = new LinearLayout(this);
        relayRow.setOrientation(LinearLayout.HORIZONTAL);
        relayInput = Ui.input(this, "", "Pin a note for Zoe...");
        relayInput.setId(R.id.eliza_relay_input);
        relayRow.addView(relayInput, new LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1.0f));
        Button relaySend = Ui.button(this, "Pin relay", Ui.GREEN, view -> sendRelay());
        relaySend.setId(R.id.eliza_relay_send);
        relayRow.addView(relaySend, sendParams);
        labRelayDrawer.addView(relayRow, Ui.margins(
                LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT, this, 4));

        labRelayDrawer.addView(Ui.section(this, "L5 Phase 5 Scorecard"));
        phase5View = Ui.text(this, "Connect to inspect or run the 5 live L5 Phase 5 pillars.", 14, Ui.TEXT);
        phase5View.setId(R.id.eliza_phase5);
        phase5View.setBackground(Ui.cardBackground(this, 18));
        phase5View.setPadding(Ui.dp(this, 16), Ui.dp(this, 14), Ui.dp(this, 16), Ui.dp(this, 14));
        phase5View.setTextIsSelectable(true);
        labRelayDrawer.addView(phase5View);
        Button runP5 = Ui.button(this, "Run Live Phase 5", Ui.COBALT, view -> runPhase5());
        runP5.setId(R.id.eliza_phase5_run);
        labRelayDrawer.addView(runP5);

        labRelayDrawer.addView(Ui.section(this, "L5 Phase 4 Scorecard"));
        phase4View = Ui.text(this, "Connect to inspect or run the 5 live L5 Phase 4 pillars.", 14, Ui.TEXT);
        phase4View.setId(R.id.eliza_phase4);
        phase4View.setBackground(Ui.cardBackground(this, 18));
        phase4View.setPadding(Ui.dp(this, 16), Ui.dp(this, 14), Ui.dp(this, 16), Ui.dp(this, 14));
        phase4View.setTextIsSelectable(true);
        labRelayDrawer.addView(phase4View);
        Button runP4 = Ui.button(this, "Run Live Phase 4", Ui.GREEN, view -> runPhase4());
        runP4.setId(R.id.eliza_phase4_run);
        labRelayDrawer.addView(runP4);

        labRelayDrawer.addView(Ui.section(this, "L5 Phase 3 Scorecard"));
        phase3View = Ui.text(this, "Connect to inspect or run the 5 live L5 Phase 3 pillars.", 14, Ui.TEXT);
        phase3View.setId(R.id.eliza_phase3);
        phase3View.setBackground(Ui.cardBackground(this, 18));
        phase3View.setPadding(Ui.dp(this, 16), Ui.dp(this, 14), Ui.dp(this, 16), Ui.dp(this, 14));
        phase3View.setTextIsSelectable(true);
        labRelayDrawer.addView(phase3View);
        Button runP3 = Ui.button(this, "Run Live Phase 3", Ui.GOLD, view -> runPhase3());
        runP3.setId(R.id.eliza_phase3_run);
        labRelayDrawer.addView(runP3);

        labRelayToggle = Ui.disclosureButton(this, "Lab Relay & L5 ▾", null);
        labRelayToggle.setOnClickListener(view -> {
            boolean open = labRelayDrawer.getVisibility() != View.VISIBLE;
            labRelayDrawer.setVisibility(open ? View.VISIBLE : View.GONE);
            labRelayToggle.setText(open ? "Lab Relay & L5 ▴" : "Lab Relay & L5 ▾");
        });
        content.addView(labRelayToggle);
        content.addView(labRelayDrawer);

        // Collapsible Drawer: Optional Online Cloud AI Settings
        LinearLayout cloudDrawer = Ui.vertical(this);
        cloudDrawer.setBackgroundColor(android.graphics.Color.TRANSPARENT);
        cloudDrawer.setVisibility(View.GONE);

        cloudKeyBadge = Ui.badge(this, "", Ui.GOLD);
        LinearLayout.LayoutParams cloudBadgeParams = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.WRAP_CONTENT, LinearLayout.LayoutParams.WRAP_CONTENT);
        cloudBadgeParams.setMargins(0, Ui.dp(this, 4), 0, Ui.dp(this, 6));
        cloudDrawer.addView(cloudKeyBadge, cloudBadgeParams);
        updateCloudBadge();
        cloudDrawer.addView(Ui.text(this,
                "Private local storage (allowBackup=false) · HTTPS only on tap.",
                13, Ui.MUTED));
        cloudKeyInput = Ui.input(this, CloudVisionClient.savedApiKey(this), "Paste optional Gemini API key");
        cloudKeyInput.setId(R.id.eliza_cloud_key);
        cloudKeyInput.setSingleLine(true);
        cloudKeyInput.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_PASSWORD);
        cloudDrawer.addView(cloudKeyInput);

        cloudModelSpinner = new Spinner(this);
        cloudModelSpinner.setId(R.id.eliza_cloud_model);
        cloudModelSpinner.setBackground(Ui.panelBackground(this, Ui.PANEL, Ui.withAlpha(Ui.GOLD, 110), 14));
        List<String> modelList = Arrays.asList(CloudVisionClient.SUPPORTED_MODELS);
        cloudModelSpinner.setAdapter(Ui.spinnerAdapter(this, modelList));
        String savedModel = CloudVisionClient.savedModel(this);
        int modelIdx = modelList.indexOf(savedModel);
        if (modelIdx >= 0) {
            cloudModelSpinner.setSelection(modelIdx);
        }
        LinearLayout.LayoutParams modelParams = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT);
        modelParams.setMargins(0, Ui.dp(this, 6), 0, Ui.dp(this, 6));
        cloudDrawer.addView(cloudModelSpinner, modelParams);

        Button saveCloud = Ui.button(this, "Save cloud key", Ui.CYAN, view -> saveCloudSettings());
        saveCloud.setId(R.id.eliza_cloud_save);
        Button clearCloud = Ui.button(this, "Clear key", Ui.RUBY, view -> {
            CloudVisionClient.saveApiKey(this, "");
            cloudKeyInput.setText("");
            updateCloudBadge();
            status.setText("Cloud Gemini API key cleared from this phone.");
        });
        cloudDrawer.addView(Ui.buttonRow(this, saveCloud, clearCloud));

        Button cloudToggle = Ui.disclosureButton(this, "Cloud AI Key ▾", null);
        cloudToggle.setOnClickListener(view -> {
            boolean open = cloudDrawer.getVisibility() != View.VISIBLE;
            cloudDrawer.setVisibility(open ? View.VISIBLE : View.GONE);
            cloudToggle.setText(open ? "Cloud AI Key ▴" : "Cloud AI Key ▾");
        });
        content.addView(cloudToggle);
        content.addView(cloudDrawer);
    }

    @Override
    protected void onResume() {
        super.onResume();
        if (chladniPad != null) {
            chladniPad.setAnimating(true);
        }
    }

    @Override
    protected void onPause() {
        if (chladniPad != null) {
            chladniPad.setAnimating(false);
        }
        if (chladniSynth != null) {
            chladniSynth.stop();
        }
        if (nativeVoice != null) {
            nativeVoice.stop();
        }
        super.onPause();
    }

    private void updateChladniLabels() {
        if (chladniPad.modeType() == ChladniPadView.MODE_SQUARE) {
            chladniModeButton.setText("Plate: Square Atelier");
            chladniInfo.setText(String.format(Locale.US,
                    "Square Atelier · Eigenmodes (%s) · Drag plate to sweep",
                    Arrays.toString(chladniPad.modes())));
        } else {
            chladniModeButton.setText("Plate: Bronze Rose Disc");
            chladniInfo.setText(String.format(Locale.US,
                    "Languidou Bronze Rose Disc · %d-fold symmetry · Touch to tune",
                    chladniPad.roseSymmetry()));
        }
    }

    private String persistEndpoint() {
        String saved = ElizaGemClient.saveEndpoint(this, endpointInput.getText().toString());
        endpointInput.setText(saved);
        return saved;
    }

    private void connectStudio() {
        String endpoint;
        try {
            endpoint = persistEndpoint();
        } catch (IllegalArgumentException error) {
            status.setText(error.getMessage());
            return;
        }
        status.setText("Connecting to " + endpoint + "…");
        executor.execute(() -> {
            try {
                ElizaGemClient.Status st = client.fetchStatus(endpoint);
                ElizaGemClient.Phase3Summary p3 = client.fetchPhase3(endpoint);
                ElizaGemClient.Phase4Summary p4 = null;
                try {
                    p4 = client.fetchPhase4(endpoint);
                } catch (Exception ignored) {
                }
                ElizaGemClient.Phase4Summary p5 = null;
                try {
                    p5 = client.fetchPhase5(endpoint);
                } catch (Exception ignored) {
                }
                ElizaGemClient.DigestResult latestDigest = null;
                try {
                    latestDigest = client.fetchLatestDigest(endpoint);
                } catch (Exception ignored) {
                }
                final ElizaGemClient.Phase4Summary p4Final = p4;
                final ElizaGemClient.Phase4Summary p5Final = p5;
                final ElizaGemClient.DigestResult digestFinal = latestDigest;
                runOnUiThread(() -> {
                    if (isFinishing() || isDestroyed()) {
                        return;
                    }
                    status.setText(String.format(Locale.US,
                            "Connected · %d rules · %d docs · LLM: %s · %d relays (%d notes)",
                            st.ruleCount, st.indexedSources,
                            st.localLlmReady ? st.localLlmLabel : "offline (Gear 1)",
                            st.relayNotesCount, st.activeNotesCount));
                    if (digestFinal != null) {
                        renderDigest(digestFinal, 0);
                    }
                    renderPhase3(p3);
                    if (p4Final != null) {
                        renderPhase4(p4Final);
                    }
                    if (p5Final != null) {
                        renderPhase5(p5Final);
                    }
                    if (labRelayDrawer != null) {
                        labRelayDrawer.setVisibility(View.VISIBLE);
                        labRelayToggle.setText("Lab Relay & L5 ▴");
                    }
                });
            } catch (Exception error) {
                runOnUiThread(() -> {
                    if (!isFinishing() && !isDestroyed()) {
                        status.setText("Workstation unreachable: " + error.getMessage()
                                + " (Offline Chladni and Cloud settings still work).");
                    }
                });
            }
        });
    }

    private void toggleGear() {
        currentGear = "gear1".equals(currentGear) ? "gear2" : "gear1";
        gearButton.setText("gear2".equals(currentGear) ? "Gear 2 · Local LLM" : "Gear 1 · ELIZA");
        status.setText("gear2".equals(currentGear)
                ? "Gear 2 selected: workstation will use local Qwen when available (0 cloud tokens)."
                : "Gear 1 selected: deterministic symbolic ELIZA + repo evidence.");
    }

    private void sendChat() {
        String msg = chatInput.getText().toString().trim();
        if (msg.isEmpty()) {
            return;
        }
        String endpoint;
        try {
            endpoint = persistEndpoint();
        } catch (IllegalArgumentException error) {
            status.setText(error.getMessage());
            return;
        }
        chatInput.setText("");
        appendTranscript("YOU · " + msg);
        status.setText("Waiting for Eliza-GEM (" + currentGear + ")…");
        executor.execute(() -> {
            try {
                ElizaGemClient.ChatReply reply = client.chat(endpoint, msg, currentGear);
                runOnUiThread(() -> {
                    if (isFinishing() || isDestroyed()) {
                        return;
                    }
                    String header = String.format(Locale.US,
                            "ELIZA-GEM [%s · %s · A_%.2f=%d/%d · %d ms · clone=%s]",
                            reply.gearUsed.toUpperCase(Locale.US), reply.mode,
                            reply.tau, reply.aTau, reply.candidateCount,
                            reply.latencyMs, reply.zoeCloneClaimed);
                    StringBuilder full = new StringBuilder(header).append('\n').append(reply.reply);
                    if (!reply.citationsSummary.isEmpty()) {
                        full.append("\nCited: ").append(reply.citationsSummary);
                    }
                    if (!reply.gear2Note.isEmpty()) {
                        full.append("\nNote: ").append(reply.gear2Note);
                    }
                    appendTranscript(full.toString());
                    status.setText("Reply received cleanly.");
                });
            } catch (Exception error) {
                runOnUiThread(() -> {
                    if (!isFinishing() && !isDestroyed()) {
                        status.setText("Eliza-GEM chat failed: " + error.getMessage());
                    }
                });
            }
        });
    }

    private void sendRelay() {
        String note = relayInput.getText().toString().trim();
        if (note.isEmpty()) {
            return;
        }
        String endpoint;
        try {
            endpoint = persistEndpoint();
        } catch (IllegalArgumentException error) {
            status.setText(error.getMessage());
            return;
        }
        relayInput.setText("");
        status.setText("Pinning lab relay for Zoe…");
        executor.execute(() -> {
            try {
                ElizaGemClient.RelayResult res = client.relay(endpoint, note, "mobile_studio");
                runOnUiThread(() -> {
                    if (!isFinishing() && !isDestroyed()) {
                        status.setText("Relay pinned cleanly (" + res.relayNotesCount
                                + " total relays, head " + shorten(res.chainHead) + ").");
                    }
                });
            } catch (Exception error) {
                runOnUiThread(() -> {
                    if (!isFinishing() && !isDestroyed()) {
                        status.setText("Relay failed: " + error.getMessage());
                    }
                });
            }
        });
    }

    private void runPhase5() {
        String endpoint;
        try {
            endpoint = persistEndpoint();
        } catch (IllegalArgumentException error) {
            status.setText(error.getMessage());
            return;
        }
        status.setText("Running live L5 Phase 5 frontier suite on workstation…");
        executor.execute(() -> {
            try {
                ElizaGemClient.Phase4Summary summary = client.runPhase5(endpoint);
                runOnUiThread(() -> {
                    if (!isFinishing() && !isDestroyed()) {
                        renderPhase5(summary);
                        status.setText("L5 Phase 5 live run finished.");
                    }
                });
            } catch (Exception error) {
                runOnUiThread(() -> {
                    if (!isFinishing() && !isDestroyed()) {
                        status.setText("L5 Phase 5 run failed: " + error.getMessage());
                    }
                });
            }
        });
    }

    private void renderPhase5(ElizaGemClient.Phase4Summary summary) {
        if (!summary.available) {
            phase5View.setText("Phase 5 report not yet generated on workstation. Tap Run Live Phase 5 to execute all 5 frontier pillars.");
            return;
        }
        StringBuilder out = new StringBuilder(String.format(Locale.US,
                "%d/%d Frontier Pillars PASS · Zoe μ=%.5f vs Control μ=%.5f\nverified=%s · l5_agi_qualified=%s · zoe_clone=%s\n\n",
                summary.pillarsPassed, summary.pillarsTotal,
                summary.meanZoeScore, summary.meanControlScore,
                summary.verified, summary.l5AgiQualified, summary.zoeCloneClaimed));
        for (String line : summary.pillarLines) {
            out.append(line).append('\n');
        }
        phase5View.setText(out.toString().trim());
    }

    private void runPhase4() {
        String endpoint;
        try {
            endpoint = persistEndpoint();
        } catch (IllegalArgumentException error) {
            status.setText(error.getMessage());
            return;
        }
        status.setText("Running live L5 Phase 4 embodied suite on workstation…");
        executor.execute(() -> {
            try {
                ElizaGemClient.Phase4Summary summary = client.runPhase4(endpoint);
                runOnUiThread(() -> {
                    if (!isFinishing() && !isDestroyed()) {
                        renderPhase4(summary);
                        status.setText("L5 Phase 4 live run finished.");
                    }
                });
            } catch (Exception error) {
                runOnUiThread(() -> {
                    if (!isFinishing() && !isDestroyed()) {
                        status.setText("L5 Phase 4 run failed: " + error.getMessage());
                    }
                });
            }
        });
    }

    private void renderPhase4(ElizaGemClient.Phase4Summary summary) {
        if (!summary.available) {
            phase4View.setText("Phase 4 report not yet generated on workstation. Tap Run Live Phase 4 to execute all 5 pillars.");
            return;
        }
        StringBuilder out = new StringBuilder(String.format(Locale.US,
                "%d/%d Pillars PASS · Zoe μ=%.5f vs Control μ=%.5f\nverified=%s · l5_agi_qualified=%s · zoe_clone=%s\n\n",
                summary.pillarsPassed, summary.pillarsTotal,
                summary.meanZoeScore, summary.meanControlScore,
                summary.verified, summary.l5AgiQualified, summary.zoeCloneClaimed));
        for (String line : summary.pillarLines) {
            out.append(line).append('\n');
        }
        phase4View.setText(out.toString().trim());
    }

    private void digestMobileToLab() {
        String endpoint;
        try {
            endpoint = persistEndpoint();
        } catch (IllegalArgumentException error) {
            status.setText(error.getMessage());
            return;
        }
        status.setText("Collecting privacy-firewalled mobile signals for Zoe Lab digestion…");
        executor.execute(() -> {
            try {
                MobileDigestionBundle.Summary bundle = MobileDigestionBundle.collect(this, brain);
                ElizaGemClient.DigestResult res = client.digestMobileBundle(endpoint, bundle.bundleJson);
                int localTotalAfter = 0;
                if (!res.refinedPrototypes.isEmpty()) {
                    localTotalAfter = VisionPriorStore.mergeRefinedFromWorkstation(this, res.refinedPrototypes);
                }
                final int localProtosFinal = localTotalAfter;
                runOnUiThread(() -> {
                    if (!isFinishing() && !isDestroyed()) {
                        renderDigest(res, localProtosFinal);
                        if (labRelayDrawer != null) {
                            labRelayDrawer.setVisibility(View.VISIBLE);
                            labRelayToggle.setText("Lab Relay & L5 ▴");
                        }
                        status.setText(String.format(Locale.US,
                                "Digestion cycle #%d complete · Zoe %.3f vs ctrl %.3f (+%.3f) · %d refined priors synced back.",
                                res.cycleNumber, res.digestedZoeScore, res.controlScore,
                                res.improvementDelta, res.refinedPrototypes.size()));
                    }
                });
            } catch (Exception error) {
                runOnUiThread(() -> {
                    if (!isFinishing() && !isDestroyed()) {
                        status.setText("Mobile digestion failed: " + error.getMessage());
                    }
                });
            }
        });
    }

    private void renderDigest(ElizaGemClient.DigestResult res, int localAppliedCount) {
        if (digestView == null) {
            return;
        }
        if (!res.available) {
            digestView.setText("No workstation digestion cycle recorded yet.\n"
                    + "Privacy Firewall active: SafeConvert, Privacy Vault, raw photos & private chat bodies are hard-excluded.\n"
                    + "Tap Feed & Digest into Zoe Lab to run your first closed-loop learning cycle.");
            return;
        }
        StringBuilder out = new StringBuilder();
        out.append(String.format(Locale.US,
                "Cycle #%d · Digested Zoe %.4f vs Control %.4f (Δ +%.4f)\n",
                res.cycleNumber, res.digestedZoeScore, res.controlScore, res.improvementDelta));
        out.append(String.format(Locale.US,
                "Ingested: +%d notes · +%d sightings · +%d visual priors (%d reinforced, %d CPC/Haeckel enriched)\n",
                res.brainNotesAdded, res.tripSightingsAdded, res.visionAdded,
                res.visionReinforced, res.visionAtlasEnriched));
        out.append(String.format(Locale.US,
                "Visual Gain: %.1f%% vs %.1f%% ctrl · Atlas Retention %.0f%% · Lab Library: %d priors · Facts: %d\n",
                res.visualAccuracy * 100.0, res.controlVisualAccuracy * 100.0,
                res.atlasRetention * 100.0, res.workstationVisionTotal, res.digestedFactsTotal));
        out.append(String.format(Locale.US,
                "Kloster τ* = %.3f · Chain: %s · Firewall=%s",
                res.recommendedTau, shorten(res.chainHead), res.firewallVerified ? "VERIFIED" : "CHECK"));
        if (localAppliedCount > 0) {
            out.append(" · Phone priors now: ").append(localAppliedCount);
        }
        out.append(String.format(Locale.US,
                "\nHonest Boundary: l5_agi_qualified=%s · zoe_clone=%s",
                res.l5AgiQualified, res.zoeCloneClaimed));
        if (!res.calibrationRationale.isEmpty()) {
            out.append("\n").append(res.calibrationRationale);
        }
        digestView.setText(out.toString());
    }

    private void syncPhoneMemory() {
        List<ZoeBrainEngine.MemoryNote> notes = brain.notesSnapshot();
        if (notes.isEmpty()) {
            status.setText("No private phone notes to sync yet. Use `remember ...` in Talk with Zoe first.");
            return;
        }
        String endpoint;
        try {
            endpoint = persistEndpoint();
        } catch (IllegalArgumentException error) {
            status.setText(error.getMessage());
            return;
        }
        status.setText("Syncing " + notes.size() + " phone notes to workstation…");
        executor.execute(() -> {
            try {
                ElizaGemClient.SyncResult res = client.syncMemory(endpoint, android.os.Build.MODEL, notes);
                runOnUiThread(() -> {
                    if (!isFinishing() && !isDestroyed()) {
                        status.setText("Unified memory synced: " + res.accepted + " added, "
                                + res.deduplicated + " already synced (head " + shorten(res.chainHead) + ").");
                    }
                });
            } catch (Exception error) {
                runOnUiThread(() -> {
                    if (!isFinishing() && !isDestroyed()) {
                        status.setText("Memory sync unreachable: " + error.getMessage());
                    }
                });
            }
        });
    }

    private void runPhase3() {
        String endpoint;
        try {
            endpoint = persistEndpoint();
        } catch (IllegalArgumentException error) {
            status.setText(error.getMessage());
            return;
        }
        status.setText("Running live L5 Phase 3 pillars on workstation…");
        executor.execute(() -> {
            try {
                ElizaGemClient.Phase3Summary summary = client.runPhase3(endpoint);
                runOnUiThread(() -> {
                    if (!isFinishing() && !isDestroyed()) {
                        renderPhase3(summary);
                        status.setText("L5 Phase 3 live run finished.");
                    }
                });
            } catch (Exception error) {
                runOnUiThread(() -> {
                    if (!isFinishing() && !isDestroyed()) {
                        status.setText("L5 Phase 3 run failed: " + error.getMessage());
                    }
                });
            }
        });
    }

    private void renderPhase3(ElizaGemClient.Phase3Summary summary) {
        if (!summary.available) {
            phase3View.setText("Phase 3 report not yet generated on workstation. Tap Run Live Phase 3 to execute all 5 pillars.");
            return;
        }
        StringBuilder out = new StringBuilder(String.format(Locale.US,
                "%d/%d Pillars PASS · Zoe μ=%.5f vs Control μ=%.5f\nverified=%s · l5_agi_qualified=%s · zoe_clone=%s\n\n",
                summary.pillarsPassed, summary.pillarsTotal,
                summary.meanZoeScore, summary.meanControlScore,
                summary.verified, summary.l5AgiQualified, summary.zoeCloneClaimed));
        for (String line : summary.pillarLines) {
            out.append(line).append('\n');
        }
        phase3View.setText(out.toString().trim());
    }

    private void appendTranscript(String line) {
        transcriptLines.add(line);
        if (transcriptLines.size() > 14) {
            transcriptLines.remove(0);
        }
        messagesView.setText(String.join("\n\n", transcriptLines));
    }

    private void updateCloudBadge() {
        if (cloudKeyBadge == null) {
            return;
        }
        boolean hasKey = !CloudVisionClient.savedApiKey(this).isEmpty();
        int accent = hasKey ? Ui.GREEN : Ui.GOLD;
        int resolved = Ui.resolveColor(this, accent);
        cloudKeyBadge.setText(hasKey ? "Cloud key: saved" : "Cloud key: not set (Share to Gemini free)");
        cloudKeyBadge.setTextColor(resolved);
        cloudKeyBadge.setBackground(Ui.panelBackground(this, Ui.withAlpha(resolved, 28), Ui.withAlpha(resolved, 150), 8));
    }

    private void saveCloudSettings() {
        String key = cloudKeyInput.getText().toString().trim();
        Object selectedModel = cloudModelSpinner.getSelectedItem();
        String model = selectedModel == null ? CloudVisionClient.DEFAULT_MODEL : selectedModel.toString();
        CloudVisionClient.saveApiKey(this, key);
        CloudVisionClient.saveModel(this, model);
        updateCloudBadge();
        status.setText(key.isEmpty()
                ? "Cloud model set to " + model + " (no API key stored; Share Photo to Gemini still works)."
                : "Cloud Gemini API key and model (" + model + ") saved locally on device.");
    }

    private static String shorten(String head) {
        return head != null && head.length() > 12 ? head.substring(0, 12) + "…" : String.valueOf(head);
    }

    @Override
    protected void onDestroy() {
        if (chladniSynth != null) {
            chladniSynth.close();
        }
        if (nativeVoice != null) {
            nativeVoice.close();
        }
        executor.shutdownNow();
        super.onDestroy();
    }
}
