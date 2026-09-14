# OTBioLab+ Button Reference Images

This folder stores reference screenshots used by the GUI to automatically
start recording in **OTBioLab+ v1.6.0** via `pyautogui` image matching.

## Required Files

### `record_button.png` (required)
A tightly-cropped screenshot of the **Record** button in OTBioLab+ when it
is in its **active / clickable** state (not greyed out).

### `play_button.png` (optional but recommended)
A tightly-cropped screenshot of the **Play** button in OTBioLab+.  If the
Record button is greyed out, the GUI will first click Play to enable it,
then click Record.

## How to Capture

1. Open **OTBioLab+ v1.6.0**.
2. Use the **Snipping Tool** (Win+Shift+S) or similar to capture **only**
   the button — crop tightly so there is minimal surrounding background.
3. Save as PNG in this folder with the exact filenames above.

## Tips

- Capture at the **same display scale / resolution** you will use during
  recording sessions (100 % scaling recommended).
- If you have `opencv-python` installed, the GUI uses fuzzy matching
  (confidence = 0.8) which is more tolerant of minor rendering differences.
  Without opencv, exact pixel matching is used.
- Re-capture the screenshots if you change your display resolution,
  Windows scaling, or OTBioLab+ version.

## Install opencv-python (recommended)

```bash
pip install opencv-python
```

This enables fuzzy image matching which is far more reliable than exact
pixel matching.
