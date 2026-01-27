import type { Page } from "@playwright/test";

const CLIPBOARD_CAPTURE_KEY = "__clipboardCapture";

export async function installClipboardCapture(page: Page, key: string) {
  await page.addInitScript(({ captureKey, storeKey }) => {
    const win = window as typeof window & {
      [key: string]: Record<string, string | null> | undefined;
    };
    if (!win[storeKey]) {
      win[storeKey] = {};
    }
    win[storeKey][captureKey] = null;

    const setCaptured = (text: string) => {
      if (!win[storeKey]) {
        win[storeKey] = {};
      }
      win[storeKey][captureKey] = text;
    };

    const ensureClipboard = () => {
      const nav = navigator as Navigator & {
        clipboard?: { writeText?: (text: string) => Promise<void> };
      };
      if (!nav.clipboard) {
        Object.defineProperty(nav, "clipboard", {
          configurable: true,
          value: {
            writeText: async (text: string) => {
              setCaptured(text);
            },
          },
        });
        return;
      }

      const original = nav.clipboard.writeText?.bind(nav.clipboard);
      nav.clipboard.writeText = async (text: string) => {
        setCaptured(text);
        if (original) {
          try {
            await original(text);
          } catch {
            // Ignore clipboard permission errors in non-HTTPS contexts.
          }
        }
      };
    };

    try {
      ensureClipboard();
    } catch {
      // Ignore errors if clipboard is not configurable.
    }
  }, { captureKey: key, storeKey: CLIPBOARD_CAPTURE_KEY });
}

export async function readClipboardCapture(page: Page, key: string) {
  return page.evaluate(({ captureKey, storeKey }) => {
    const win = window as typeof window & {
      [key: string]: Record<string, string | null> | undefined;
    };
    return win[storeKey]?.[captureKey] ?? null;
  }, { captureKey: key, storeKey: CLIPBOARD_CAPTURE_KEY });
}
