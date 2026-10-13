# Solid Stud Survivor

[繁體中文](README.md)

Solid Stud Survivor is a Windows GUI tool that converts OBJ or STL models into the three files used by Stud.io custom parts: `.dat`, `.col`, and `.conn`.

## Requirements

- 64-bit Windows 10 or later
- Python 3.11 or newer (Python 3.11 is confirmed to work)
- NumPy
- `fast-simplification` is optional and only required for mesh reduction

## Install and launch

1. Install Python 3.11 or newer and enable the option to add Python to PATH.
2. Open a terminal in this folder and install the required package:

   ```powershell
   py -3.11 -m pip install -r requirements.txt
   ```

3. Double-click `obj2stud_gui.pyw` to open the application.

To enable mesh reduction, install the optional package:

```powershell
py -3.11 -m pip install fast-simplification
```

## Using the GUI

Use the language selector in the upper-right corner to switch between Traditional Chinese and English.

1. Select an `.obj` or `.stl` model.
2. The application scans the model and lists object names and face counts. Select the objects to export; all objects are selected by default.
3. The default output root is `%LOCALAPPDATA%\Stud.io\CustomParts`. The application places the files in the `parts`, `collider`, and `connectivity` subfolders. You can choose a different output root in the window.
4. Set either the finished width in millimeters or studs (1 stud = 7.8 mm), or enter a model-unit-to-millimeter scale.
5. Adjust the minimum piece size, face-reduction target, or Z-up option if needed, then click **Start Conversion**. The minimum piece size defaults to 0 (no removal) to avoid accidentally deleting model details.

After conversion, the message panel shows the model's width, height, and length in both millimeters and studs.

Input models are assumed to use Y-up coordinates. Enable the Z-up option for models that use Z as the up axis. The output is centered in X/Z, rests at Y=0, and uses the LDraw coordinate system.

OBJ `o` objects are listed as selectable components; `g` groups are used only when the OBJ has no `o` objects. OBJ material colors are not currently imported, so output triangles use the Stud.io part's main color. If a referenced `.mtl` file is missing, its source color information is unavailable.

## Command-line conversion

The command-line converter can also be used in PowerShell:

```powershell
py -3.11 .\obj2stud.py .\model.obj --width 85.8 --out .\parts
```

To see all available options:

```powershell
py -3.11 .\obj2stud.py --help
```
