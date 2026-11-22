package research.zoetic.zoe;

import android.content.ActivityNotFoundException;
import android.content.ClipData;
import android.content.ClipboardManager;
import android.content.Context;
import android.content.Intent;
import android.graphics.Color;
import android.os.Bundle;
import android.view.ViewGroup;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

import androidx.activity.ComponentActivity;

import java.security.KeyPair;
import java.security.PublicKey;

/**
 * Zoe Privacy & Signal-Grade E2EE Vault (v0.6.0-beta).
 *
 *   - Hardware-backed AndroidKeyStore AES-256-GCM at-rest encryption status for private chats
 *   - Verifiable 60-digit Signal-style Safety Number fingerprint
 *   - Peer-to-peer ECDH + HKDF-SHA256 + Symmetric Chain Ratchet + AES-256-GCM Seal / Unseal tool
 *   - Direct 1-tap handoff to share encrypted envelopes via Signal (`org.thoughtcrime.securesms`) or any app.
 */
public final class PrivacyVaultActivity extends ComponentActivity {
    private KeyPair deviceIdentity;
    private String myPubB64 = "";

    private TextView status;
    private TextView safetyNumberView;
    private TextView pubKeyView;
    private EditText peerKeyInput;
    private EditText messageInput;
    private TextView outputBox;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        LinearLayout root = Ui.vertical(this);
        root.setBackgroundColor(Color.TRANSPARENT);

        LinearLayout header = Ui.vertical(this);
        header.setBackgroundColor(Color.TRANSPARENT);
        header.setPadding(Ui.dp(this, 16), Ui.dp(this, 4), Ui.dp(this, 16), Ui.dp(this, 2));
        header.addView(Ui.topBar(this, "Privacy Vault", null));
        root.addView(header);

        ScrollView scroll = new ScrollView(this);
        scroll.setFillViewport(true);
        scroll.setBackgroundColor(Color.TRANSPARENT);
        LinearLayout body = Ui.vertical(this);
        body.setBackgroundColor(Color.TRANSPARENT);
        body.setPadding(Ui.dp(this, 16), Ui.dp(this, 8), Ui.dp(this, 16), Ui.dp(this, 32));

        boolean hw = ZoeSignalCrypto.isHardwareKeystoreActive();
        status = Ui.statusBanner(this,
                hw ? "🔒 Hardware-backed encryption active"
                        : "🔒 On-device AES-256 encryption active",
                Ui.GREEN);
        status.setId(R.id.vault_status);
        body.addView(status);

        // 1. Clean 60-Digit Safety Number Card
        LinearLayout fpCard = Ui.vertical(this);
        fpCard.setBackground(Ui.cardBackground(this, 20));
        fpCard.setPadding(Ui.dp(this, 16), Ui.dp(this, 16), Ui.dp(this, 16), Ui.dp(this, 16));
        LinearLayout.LayoutParams cardLp = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        cardLp.setMargins(0, Ui.dp(this, 8), 0, Ui.dp(this, 12));

        TextView fpTitle = Ui.text(this, "Safety Number", 15f, Ui.TEXT);
        fpTitle.setTypeface(Ui.SANS_MEDIUM);
        fpCard.addView(fpTitle);
        safetyNumberView = Ui.text(this, "Generating key…", 16.5f, Ui.TEXT);
        safetyNumberView.setId(R.id.vault_safety_number);
        safetyNumberView.setTypeface(android.graphics.Typeface.MONOSPACE);
        safetyNumberView.setLetterSpacing(0.05f);
        safetyNumberView.setTextIsSelectable(true);
        safetyNumberView.setPadding(0, Ui.dp(this, 8), 0, Ui.dp(this, 8));
        fpCard.addView(safetyNumberView);

        pubKeyView = Ui.text(this, "", 12f, Ui.MUTED);
        pubKeyView.setTextIsSelectable(true);
        pubKeyView.setPadding(0, 0, 0, Ui.dp(this, 10));
        fpCard.addView(pubKeyView);

        Button copyKeyBtn = Ui.button(this, "Copy Key", Ui.COBALT, v -> copyText("Zoe Public Key", myPubB64));
        Button shareKeySignalBtn = Ui.button(this, "Share Key ↗", Ui.CYAN, v -> shareViaSignalOrSheet("My Zoe Public Key:\n" + myPubB64));
        fpCard.addView(Ui.buttonRow(this, copyKeyBtn, shareKeySignalBtn));
        body.addView(fpCard, cardLp);

        // 2. Clean Encrypt / Decrypt Note Card
        LinearLayout e2eeCard = Ui.vertical(this);
        e2eeCard.setBackground(Ui.cardBackground(this, 20));
        e2eeCard.setPadding(Ui.dp(this, 16), Ui.dp(this, 16), Ui.dp(this, 16), Ui.dp(this, 16));
        TextView sealTitle = Ui.text(this, "Encrypt a Note", 15f, Ui.TEXT);
        sealTitle.setTypeface(Ui.SANS_MEDIUM);
        e2eeCard.addView(sealTitle);
        TextView sealSub = Ui.text(this, "ECDH + AES-256-GCM · stays on your device", 12f, Ui.MUTED);
        sealSub.setPadding(0, 0, 0, Ui.dp(this, 6));
        e2eeCard.addView(sealSub);

        peerKeyInput = styledInput("Recipient public key (blank for yourself)");
        peerKeyInput.setId(R.id.vault_peer_key);
        e2eeCard.addView(peerKeyInput);

        messageInput = styledInput("Write a note — or paste ZOE-SIGNAL-V1:…");
        messageInput.setId(R.id.vault_message_input);
        e2eeCard.addView(messageInput);

        Button sealBtn = Ui.primaryButton(this, "🔒 Lock Note", Ui.COBALT, v -> doSeal());
        sealBtn.setId(R.id.vault_seal_btn);
        Button openBtn = Ui.button(this, "🔓 Unlock", Ui.GREEN, v -> doUnseal());
        openBtn.setId(R.id.vault_unseal_btn);
        e2eeCard.addView(Ui.buttonRow(this, sealBtn, openBtn));

        outputBox = Ui.text(this, "Locked or unlocked note appears here.", 13f, Ui.MUTED);
        outputBox.setId(R.id.vault_output);
        outputBox.setTextIsSelectable(true);
        outputBox.setPadding(Ui.dp(this, 14), Ui.dp(this, 12), Ui.dp(this, 14), Ui.dp(this, 12));
        outputBox.setBackground(Ui.tonalPillDrawable(this, Ui.tonalWellColor(this), Ui.primaryAccent(this), 16));
        LinearLayout.LayoutParams outLp = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        outLp.setMargins(0, Ui.dp(this, 10), 0, Ui.dp(this, 10));
        e2eeCard.addView(outputBox, outLp);

        Button copyOutBtn = Ui.button(this, "Copy", Ui.MUTED, v -> copyText("Zoe Vault Note", outputBox.getText().toString()));
        Button sendSignalBtn = Ui.primaryButton(this, "Share ↗", Ui.CYAN, v -> shareViaSignalOrSheet(outputBox.getText().toString()));
        e2eeCard.addView(Ui.buttonRow(this, copyOutBtn, sendSignalBtn));
        body.addView(e2eeCard, cardLp);

        scroll.addView(body);
        root.addView(scroll, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f));

        setContentView(Ui.wrapWithBackdrop(this, root));
        Ui.configureEdgeToEdge(this, root);

        initDeviceIdentity();
    }

    private EditText styledInput(String hint) {
        EditText et = new EditText(this);
        et.setHint(hint);
        et.setTextColor(Ui.textColor(this));
        et.setHintTextColor(Ui.mutedColor(this));
        et.setTextSize(13.5f);
        et.setBackground(Ui.tonalPillDrawable(this, Ui.tonalWellColor(this), Ui.primaryAccent(this), 14));
        et.setPadding(Ui.dp(this, 12), Ui.dp(this, 10), Ui.dp(this, 12), Ui.dp(this, 10));
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        lp.setMargins(0, Ui.dp(this, 6), 0, Ui.dp(this, 6));
        et.setLayoutParams(lp);
        return et;
    }

    private void initDeviceIdentity() {
        try {
            deviceIdentity = ZoeSignalCrypto.getOrCreateDeviceIdentity(this);
            myPubB64 = ZoeSignalCrypto.encodePublicKey(deviceIdentity.getPublic());
            byte[] pubBytes = deviceIdentity.getPublic().getEncoded();
            String safety = ZoeSignalCrypto.computeSafetyNumber(pubBytes, pubBytes);
            safetyNumberView.setText(safety);
            pubKeyView.setText("Public Identity (EC P-256): " + myPubB64.substring(0, Math.min(36, myPubB64.length())) + "…");
        } catch (Exception err) {
            safetyNumberView.setText("Key setup error: " + err.getMessage());
        }
    }

    private void doSeal() {
        String msg = messageInput.getText() == null ? "" : messageInput.getText().toString().trim();
        if (msg.isEmpty()) {
            status.setText("Type a private note above first, then tap Seal E2EE Envelope.");
            return;
        }
        try {
            String peerStr = peerKeyInput.getText() == null ? "" : peerKeyInput.getText().toString().trim();
            PublicKey target = peerStr.isEmpty() ? deviceIdentity.getPublic() : ZoeSignalCrypto.decodePublicKey(peerStr);
            String sealed = ZoeSignalCrypto.sealForPeer(target, msg);
            outputBox.setText(sealed);
            if (!peerStr.isEmpty()) {
                safetyNumberView.setText(ZoeSignalCrypto.computeSafetyNumber(
                        deviceIdentity.getPublic().getEncoded(), target.getEncoded()));
            }
            status.setText("Locked cleanly (" + sealed.length() + " chars · AES-256-GCM).");
        } catch (Exception err) {
            status.setText("Could not lock note: " + err.getMessage());
        }
    }

    private void doUnseal() {
        String raw = messageInput.getText() == null ? "" : messageInput.getText().toString().trim();
        if (!raw.startsWith(ZoeSignalCrypto.ENVELOPE_PREFIX)) {
            raw = outputBox.getText() == null ? "" : outputBox.getText().toString().trim();
        }
        try {
            String plain = ZoeSignalCrypto.openFromPeer(deviceIdentity.getPrivate(), raw);
            outputBox.setText(plain);
            status.setText("Verified & unlocked on-device.");
        } catch (Exception err) {
            status.setText("Could not unlock (wrong key or altered text).");
        }
    }

    private void copyText(String label, String text) {
        ClipboardManager cm = (ClipboardManager) getSystemService(Context.CLIPBOARD_SERVICE);
        if (cm != null && text != null && !text.isEmpty()) {
            cm.setPrimaryClip(ClipData.newPlainText(label, text));
            status.setText("Copied " + label + " to clipboard.");
        }
    }

    private void shareViaSignalOrSheet(String body) {
        if (body == null || body.trim().isEmpty()) {
            return;
        }
        Intent sig = new Intent(Intent.ACTION_SEND)
                .setType("text/plain")
                .setPackage(ZoeSignalCrypto.SIGNAL_PACKAGE)
                .putExtra(Intent.EXTRA_TEXT, body);
        try {
            startActivity(sig);
            status.setText("Handed off to Signal.");
            return;
        } catch (ActivityNotFoundException ignored) {
        }
        Intent sheet = new Intent(Intent.ACTION_SEND)
                .setType("text/plain")
                .putExtra(Intent.EXTRA_TEXT, body);
        startActivity(Intent.createChooser(sheet, "Share via encrypted messenger"));
    }
}
