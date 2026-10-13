# Solid Stud Survivor

[English](README.en.md)

Solid Stud Survivor 是一款 Windows 視窗工具，可將 OBJ 或 STL 模型轉成 Stud.io 自訂零件所需的 `.dat`、`.col`、`.conn` 三個檔案。

## 環境需求

- Windows 10 或更新版本，64 位元
- Python 3.12
- NumPy
- 若要使用減面功能，需另外安裝 `fast-simplification`

## 安裝與啟動

1. 安裝 Python 3.12，安裝時啟用將 Python 加入 PATH 的選項。
2. 在本資料夾開啟終端機，執行：

   ```powershell
   py -3.12 -m pip install -r requirements.txt
   ```

3. 雙擊 `obj2stud_gui.pyw` 開啟視窗。

如要使用減面功能，額外執行：

```powershell
py -3.12 -m pip install fast-simplification
```

## 視窗操作

1. 選擇 `.obj` 或 `.stl` 模型檔案。
2. 選檔後程式會讀取物件名稱與面數，勾選要輸出的物件（預設全選）。
3. 預設輸出根資料夾為 `%LOCALAPPDATA%\Stud.io\CustomParts`，程式會將三種檔案分別放入 `parts`、`collider`、`connectivity` 子資料夾；也可在視窗選擇其他輸出根資料夾。
4. 設定成品寬度（mm）或模型單位轉換倍率，兩者擇一。
5. 視需要調整小碎片下限、減面目標或 Z 朝上選項，再按「開始轉換」。

輸入模型預設為 Y 朝上；Z 朝上的模型需勾選對應選項。輸出會將 X/Z 置中、底部放在 Y=0，並依 LDraw 座標系輸出。

## 命令列參數

查看所有參數：

```powershell
py -3.12 .\obj2stud.py --help
```

## 命令列轉換範例

也可在 PowerShell 使用命令列版本：

```powershell
py -3.12 .\obj2stud.py .\model.obj --width 85.8 --out .\parts
```
