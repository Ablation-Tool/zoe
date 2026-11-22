package research.zoetic.zoe;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

import android.view.WindowManager;
import android.webkit.WebView;

import androidx.test.ext.junit.rules.ActivityScenarioRule;
import androidx.test.ext.junit.runners.AndroidJUnit4;

import org.junit.Before;
import org.junit.Rule;
import org.junit.Test;
import org.junit.runner.RunWith;

import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicReference;

@RunWith(AndroidJUnit4.class)
public class SafeConvertActivityTest {
    @Rule
    public ActivityScenarioRule<SafeConvertActivity> activity = new ActivityScenarioRule<>(SafeConvertActivity.class);

    @Before
    public void waitForConverter() throws Exception {
        long deadline = System.nanoTime() + TimeUnit.SECONDS.toNanos(10);
        while (System.nanoTime() < deadline) {
            String ready = evaluate("document.readyState === 'complete' && !!document.getElementById('help') && document.body.innerText.includes('UNIT CONVERTER')");
            if (ready.contains("true")) {
                return;
            }
            Thread.sleep(50);
        }
        throw new AssertionError("SafeConvert did not finish loading");
    }

    @Test
    public void converterRunsLocallyWithoutReactOrCdn() throws Exception {
        assertTrue("Help state=" + evaluate("document.getElementById('help').className + ':' + getComputedStyle(document.getElementById('help')).display"),
                evaluate("getComputedStyle(document.getElementById('help')).display").contains("none"));
        String text = evaluate("document.body.innerText");
        assertTrue(text.contains("UNIT CONVERTER"));
        assertFalse(text.contains("cdnjs"));
        assertTrue(evaluate("document.getElementById('result').textContent").contains("—"));
    }

    @Test
    public void conversionUsesRealUnits() throws Exception {
        evaluate("document.getElementById('to').value='Centimeters';document.getElementById('value').value='1';document.getElementById('value').dispatchEvent(new Event('input'));''");
        String result = evaluate("document.getElementById('result').textContent");
        assertTrue(result.contains("2.54"));
    }

    @Test
    public void normalDecimalsIncludingZeroNeverFalseTrigger() throws Exception {
        for (String v : new String[]{"0", "0.00", "112", "0.5"}) {
            evaluate("document.getElementById('value').value='" + v + "';document.getElementById('value').dispatchEvent(new Event('input'));''");
            assertTrue("Expected converter to stay active for value " + v,
                    evaluate("getComputedStyle(document.getElementById('help')).display").contains("none"));
        }
    }

    @Test
    public void allFourCategoriesAndSwapConvertAccurately() throws Exception {
        evaluate("document.getElementById('category').value='Length';document.getElementById('category').dispatchEvent(new Event('change'));"
                + "document.getElementById('from').value='Inches';document.getElementById('to').value='Centimeters';"
                + "document.getElementById('value').value='100';document.getElementById('value').dispatchEvent(new Event('input'));''");
        assertEquals("\"254\"", evaluate("document.getElementById('result').textContent"));

        evaluate("Array.from(document.querySelectorAll('.cat-tab')).find(b=>b.textContent==='Weight').click();"
                + "document.getElementById('from').value='Pounds';document.getElementById('to').value='Ounces';"
                + "document.getElementById('value').value='1';document.getElementById('value').dispatchEvent(new Event('input'));''");
        assertEquals("\"16\"", evaluate("document.getElementById('result').textContent"));

        evaluate("Array.from(document.querySelectorAll('.cat-tab')).find(b=>b.textContent==='Temperature').click();"
                + "document.getElementById('value').value='212';document.getElementById('value').dispatchEvent(new Event('input'));''");
        assertEquals("\"100\"", evaluate("document.getElementById('result').textContent"));

        evaluate("document.getElementById('swap').click();document.getElementById('value').value='0';document.getElementById('value').dispatchEvent(new Event('input'));''");
        assertEquals("\"32\"", evaluate("document.getElementById('result').textContent"));

        evaluate("Array.from(document.querySelectorAll('.cat-tab')).find(b=>b.textContent==='Volume').click();"
                + "document.getElementById('from').value='Gallons';document.getElementById('to').value='Cups';"
                + "document.getElementById('value').value='1';document.getElementById('value').dispatchEvent(new Event('input'));''");
        assertEquals("\"16\"", evaluate("document.getElementById('result').textContent"));
    }

    @Test
    public void emergencyCodeVariantsRevealHelpAndRestoredLegalSection() throws Exception {
        evaluate("document.getElementById('value').value='9.11';document.getElementById('value').dispatchEvent(new Event('input'));''");
        assertEquals("\"\"", evaluate("document.getElementById('value').value"));
        assertFalse(evaluate("getComputedStyle(document.getElementById('help')).display").contains("none"));
        String helpText = evaluate("document.body.innerText");
        assertTrue(helpText.contains("You are not alone."));
        assertTrue(helpText.contains("My safe people"));
        assertTrue(helpText.contains("Talk to Zoe"));
        assertTrue(helpText.contains("Can I get legal help?"));

        evaluate("Array.from(document.querySelectorAll('.acc-btn')).find(b=>b.textContent.includes('Can I get legal help?')).click();''");
        String legalBody = evaluate("document.getElementById('helpSections').innerText");
        assertTrue(legalBody.contains("protection order"));
        assertTrue(evaluate("document.getElementById('helpSections').innerHTML").contains("https://lawhelp.org"));

        evaluate("exitHelp();''");
        assertTrue(evaluate("getComputedStyle(document.getElementById('help')).display").contains("none"));
        assertFalse(evaluate("document.body.innerText").contains("You are not alone"));
    }

    @Test
    public void safeContactsPersistAcrossActivityRecreationAndToggleFlagSecure() throws Exception {
        evaluate("if(window.SafeStore){SafeStore.saveContacts('[]');}localStorage.removeItem('uc_pref_v1');"
                + "document.getElementById('value').value='0911';document.getElementById('value').dispatchEvent(new Event('input'));''");
        assertFalse(evaluate("getComputedStyle(document.getElementById('help')).display").contains("none"));
        waitForFlagSecure(true);

        evaluate("document.getElementById('contactsToggle').click();"
                + "document.getElementById('addContact').click();"
                + "Array.from(document.querySelectorAll('.chip')).find(c=>c.textContent==='Blue sky').click();"
                + "document.getElementById('contactName').value='Mom';"
                + "document.getElementById('contactPhone').value='555-0199';"
                + "document.getElementById('saveContact').click();''");

        String savedHtml = evaluate("document.getElementById('contacts').innerHTML");
        assertTrue(savedHtml.contains("sms:5550199?body=Blue%20sky"));
        assertTrue(savedHtml.contains("tel:5550199"));
        assertTrue(evaluate("window.SafeStore.loadContacts()").contains("Mom"));

        activity.getScenario().recreate();
        waitForConverter();
        assertTrue(evaluate("getComputedStyle(document.getElementById('help')).display").contains("none"));
        assertFalse(hasFlagSecure());

        evaluate("document.getElementById('value').value='919';document.getElementById('value').dispatchEvent(new Event('input'));''");
        waitForFlagSecure(true);
        assertEquals("\"true\"", evaluate("document.getElementById('contactsToggle').getAttribute('aria-expanded')"));
        String persistedText = evaluate("document.getElementById('contacts').innerText");
        assertTrue(persistedText.contains("Mom"));
        assertTrue(persistedText.contains("555-0199"));
        assertTrue(persistedText.contains("Blue sky"));

        evaluate("Array.from(document.querySelectorAll('#contacts button')).find(b=>b.textContent==='Edit').click();"
                + "document.getElementById('contactName').value='Aunt Sarah';"
                + "document.getElementById('saveContact').click();''");
        assertTrue(evaluate("document.getElementById('contacts').innerText").contains("Aunt Sarah"));

        evaluate("Array.from(document.querySelectorAll('#contacts button')).find(b=>b.textContent==='Edit').click();"
                + "document.getElementById('deleteAsk').click();"
                + "document.getElementById('deleteYes').click();''");
        assertEquals("\"[]\"", evaluate("window.SafeStore.loadContacts()"));
        assertFalse(evaluate("document.getElementById('contacts').innerText").contains("Aunt Sarah"));

        evaluate("exitHelp();''");
        waitForFlagSecure(false);
    }

    @Test
    public void talkToZoeCalmsAndLogsTimestampedProofAcrossRecreation() throws Exception {
        evaluate("if(window.SafeStore){SafeStore.clearAllEvidence();}localStorage.removeItem('uc_log_v1');"
                + "document.getElementById('value').value='911';document.getElementById('value').dispatchEvent(new Event('input'));"
                + "document.getElementById('zoeToggle').click();''");

        assertTrue(evaluate("window.SafeStore.supportsMediaVault()").contains("true"));
        assertFalse(evaluate("getComputedStyle(document.getElementById('mediaRecRow')).display").contains("none"));
        String recText = evaluate("document.getElementById('mediaRecRow').innerText");
        assertTrue(recText.contains("Record audio"));
        assertTrue(recText.contains("Record video"));

        evaluate("Array.from(document.querySelectorAll('.zoe-chip')).find(c=>c.textContent.includes('sad')).click();''");
        assertTrue(evaluate("document.getElementById('zoeChat').innerText").contains("ZOE"));

        evaluate("document.getElementById('breathBtn').click();''");
        assertFalse(evaluate("getComputedStyle(document.getElementById('breathBox')).display").contains("none"));
        evaluate("document.getElementById('breathBtn').click();''");
        assertTrue(evaluate("getComputedStyle(document.getElementById('breathBox')).display").contains("none"));

        evaluate("document.getElementById('logInput').value='Yelled threats in hallway';"
                + "document.getElementById('logSaveBtn').click();''");
        String logText = evaluate("document.getElementById('evidenceList').innerText");
        assertTrue(logText.contains("Yelled threats in hallway"));
        assertTrue(logText.contains("SHA-256:"));

        activity.getScenario().recreate();
        waitForConverter();

        evaluate("document.getElementById('value').value='119';document.getElementById('value').dispatchEvent(new Event('input'));"
                + "document.getElementById('zoeToggle').click();''");
        assertEquals("\"\"", evaluate("document.getElementById('zoeChat').innerText"));
        String persistedLog = evaluate("document.getElementById('evidenceList').innerText");
        assertTrue(persistedLog.contains("Yelled threats in hallway"));
        assertTrue(persistedLog.contains("SHA-256:"));

        evaluate("document.getElementById('wipeLogAsk').click();"
                + "document.getElementById('wipeLogYes').click();''");
        assertEquals("\"[]\"", evaluate("window.SafeStore.loadEvidence()"));
        evaluate("exitHelp();''");
    }

    @Test
    public void privateVaultPasscodeLocksOnExitAndShareRequiresExplicitPermission() throws Exception {
        try {
            evaluate("document.getElementById('value').value='911';document.getElementById('value').dispatchEvent(new Event('input'));"
                    + "document.getElementById('zoeToggle').click();''");
            assertTrue(evaluate("document.getElementById('privacyBanner').innerText").contains("PRIVATE · USER + ZOE ONLY"));

            evaluate("document.getElementById('logInput').value='Private test entry';"
                    + "document.getElementById('logSaveBtn').click();''");

            evaluate("document.getElementById('vaultPassToggle').click();"
                    + "document.getElementById('vaultPassInput').value='7429';"
                    + "document.getElementById('vaultPassSaveBtn').click();''");
            assertTrue(evaluate("window.SafeStore.hasVaultPasscode()").contains("true"));

            // Exiting must auto-lock the private vault
            evaluate("exitHelp();''");
            evaluate("document.getElementById('value').value='911';document.getElementById('value').dispatchEvent(new Event('input'));"
                    + "document.getElementById('zoeToggle').click();''");

            assertTrue(evaluate("window.SafeStore.isVaultUnlocked()").contains("false"));
            assertEquals("\"[]\"", evaluate("window.SafeStore.loadEvidence()"));
            assertFalse(evaluate("getComputedStyle(document.getElementById('vaultLockGate')).display").contains("none"));
            assertTrue(evaluate("getComputedStyle(document.getElementById('evidenceList')).display").contains("none"));

            // Wrong passcode stays locked
            evaluate("document.getElementById('vaultUnlockInput').value='0000';"
                    + "document.getElementById('vaultUnlockBtn').click();''");
            assertTrue(evaluate("window.SafeStore.isVaultUnlocked()").contains("false"));
            assertTrue(evaluate("document.getElementById('vaultLockError').innerText").contains("Incorrect passcode"));

            // Correct passcode unlocks
            evaluate("document.getElementById('vaultUnlockInput').value='7429';"
                    + "document.getElementById('vaultUnlockBtn').click();''");
            assertTrue(evaluate("window.SafeStore.isVaultUnlocked()").contains("true"));
            assertTrue(evaluate("document.getElementById('evidenceList').innerText").contains("Private test entry"));

            // Sharing requires explicit second confirmation step (Keep private vs Grant permission)
            evaluate("Array.from(document.querySelectorAll('#evidenceList button')).find(b=>b.textContent==='Share').click();''");
            assertTrue(evaluate("document.getElementById('evidenceList').innerText").contains("Grant permission"));
            evaluate("Array.from(document.querySelectorAll('#evidenceList button')).find(b=>b.textContent==='Keep private').click();''");
            assertFalse(evaluate("document.getElementById('evidenceList').innerText").contains("Grant permission"));

            // Remove passcode & clean test entry
            evaluate("document.getElementById('vaultPassToggle').click();"
                    + "document.getElementById('vaultPassInput').value='7429';"
                    + "document.getElementById('vaultPassSaveBtn').click();''");
            assertTrue(evaluate("window.SafeStore.hasVaultPasscode()").contains("false"));
            evaluate("document.getElementById('wipeLogAsk').click();"
                    + "document.getElementById('wipeLogYes').click();''");
            assertEquals("\"[]\"", evaluate("window.SafeStore.loadEvidence()"));
            evaluate("exitHelp();''");
        } finally {
            activity.getScenario().onActivity(act -> {
                SafeVaultLock.clearPasscode(act);
                SafeEvidenceStore.clearAll(SafeEvidenceStore.vaultDir(act));
            });
        }
    }

    @Test
    public void exitLeavesOnlyTheConverterCover() throws Exception {
        evaluate("exitHelp();''");
        assertTrue("Help state=" + evaluate("document.getElementById('help').className + ':' + getComputedStyle(document.getElementById('help')).display"),
                evaluate("getComputedStyle(document.getElementById('help')).display").contains("none"));
        assertTrue(evaluate("getComputedStyle(document.getElementById('converter')).display").contains("block"));
        assertFalse(evaluate("document.body.innerText").contains("You are not alone"));
    }

    private boolean hasFlagSecure() {
        AtomicBoolean secured = new AtomicBoolean(false);
        activity.getScenario().onActivity(act -> secured.set(
                (act.getWindow().getAttributes().flags & WindowManager.LayoutParams.FLAG_SECURE) != 0));
        return secured.get();
    }

    private void waitForFlagSecure(boolean expected) throws Exception {
        long deadline = System.nanoTime() + TimeUnit.SECONDS.toNanos(5);
        while (System.nanoTime() < deadline) {
            if (hasFlagSecure() == expected) {
                return;
            }
            Thread.sleep(40);
        }
        assertEquals(expected, hasFlagSecure());
    }

    private String evaluate(String script) throws Exception {
        CountDownLatch latch = new CountDownLatch(1);
        AtomicReference<String> result = new AtomicReference<>("");
        activity.getScenario().onActivity(activity -> {
            WebView view = activity.findViewById(R.id.safe_web);
            view.evaluateJavascript(script, value -> {
                result.set(value == null ? "" : value);
                latch.countDown();
            });
        });
        assertTrue(latch.await(8, TimeUnit.SECONDS));
        return result.get();
    }
}
