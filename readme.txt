exe 실행파일 만드는 방법
python -m PyInstaller --onefile --noconfirm --clean -n search search.py  

.\search.exe -F "F:\Tops_Sample\RP_104162_Military (1)\nexacroCom\typedefinition.xml" -K "../"

.\search.exe -F "F:\Tops_Sample\RP_104162_Military (1)\nexacroCom\typedefinition.xml" -K "../" --extract-pair "prefixid,url"
python search.py C:\Users\sjrnfl13\python\config.json
python search.py -F "F:\Tops_Sample\RP_104162_Military (1)\nexacroCom\typedefinition.xml" -K "../"
py -OO -m nuitka --standalone  --onefile search.py --remove-output --product-name="Deploy Test"  --product-version="0.0.0.1"  --file-version="2026.1.19.1"  --file-description="Deploy Test"  --company-name="TOBESOFT Co., Ltd."  --output-filename="search"