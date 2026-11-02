# PDF Editor Pro

PDF editor for Windows by MKBSoft: edit text, read and print, merge, split, rotate, compress,
annotate, sign, password-protect, convert to Word/Excel/PowerPoint/images/EPUB and send to Kindle.
Interface in 8 languages (EN, TR, DE, ES, FR, IT, PT, RU).

- Microsoft Store: https://apps.microsoft.com/detail/9PJJ019JKTP9
- Website: https://mkbsoft.net

## License

PDF Editor Pro is free software: you can redistribute it and/or modify it under the terms of the
**GNU Affero General Public License version 3** (AGPL-3.0) as published by the Free Software
Foundation. See [LICENSE](LICENSE). This program is distributed WITHOUT ANY WARRANTY.

Copyright © 2026 MKBSoft (destek@mkbsoft.net)

**Additional term (AGPL-3.0 section 7(e)):** this license does not grant rights to the name
"PDF Editor Pro", the MKBSoft name or the PDF Editor Pro logo and icons. A modified version that
you distribute must use a different name and icon.

The program uses [PyMuPDF](https://pymupdf.readthedocs.io/) (AGPL-3.0 / Artifex commercial
license) and other third-party components; their licenses are listed in
[static/THIRD_PARTY_LICENSES.txt](static/THIRD_PARTY_LICENSES.txt) and in the program's
**About** window. Each release is tagged (`vX.Y.Z`) so the source of every published version can
be found.

The paid full version (Microsoft Store add-on or license key) pays for development, Store
distribution, automatic updates and support.

## Building from source

Windows 10/11, Python 3.13:

```
pip install pymupdf flask pywebview pdf2docx python-docx python-pptx openpyxl docx2pdf ^
            winrt-runtime winrt-Windows.Services.Store winrt-Windows.Foundation ^
            winrt-Windows.Foundation.Collections pyinstaller
python app.py                       # run
python make_third_party.py          # refresh the third-party license list
python -m PyInstaller pdf_editor.spec --noconfirm
python build_msix.py <version> <path to makeappx.exe>   # optional: MSIX package
```

The license server (`worker.js`, Cloudflare Worker) is a separate program and is not part of
this repository.

---

## Türkçe

PDF Editor Pro, MKBSoft tarafından geliştirilen bir Windows PDF düzenleyicisidir. **GNU Affero
Genel Kamu Lisansı sürüm 3 (AGPL-3.0)** ile lisanslanmış özgür yazılımdır: kaynak kodunu
inceleyebilir, değiştirebilir ve lisans koşullarına uyarak dağıtabilirsiniz. "PDF Editor Pro"
adı, MKBSoft adı ve program logosu bu lisansın kapsamında değildir (AGPL-3.0 madde 7(e));
değiştirilmiş sürümler farklı bir ad ve simgeyle dağıtılmalıdır.

Ücretli tam sürüm (Microsoft Store eklentisi veya lisans anahtarı); geliştirmeyi, Store üzerinden
kurulumu, otomatik güncellemeleri ve desteği karşılar.
