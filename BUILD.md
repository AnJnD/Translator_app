# Build Instructions

## Prerequisites

- Python 3.10 or higher
- pip

## Install Dependencies

```bash
pip install -r requirements.txt
```

## Build on Windows

```bash
pyinstaller translator_meeting.spec
```

Output: `dist/MeetingTranslator.exe`

To add a custom icon, place `icon.ico` in the project root before building.

## Build on macOS

```bash
pyinstaller translator_meeting.spec
```

Output: `dist/MeetingTranslator.app`

To add a custom icon, place `icon.icns` in the project root before building.

### Optional: Create a .dmg installer

```bash
hdiutil create -volname "MeetingTranslator" -srcfolder dist/MeetingTranslator.app -ov -format UDZO dist/MeetingTranslator.dmg
```

## Output Location

All build artifacts are placed in the `dist/` directory.
