exe 실행파일 만드는 방법
python -m PyInstaller --onefile --noconfirm --clean -n search search.py  

.\search.exe -F "F:\Tops_Sample\RP_104162_Military (1)\nexacroCom\typedefinition.xml" -K "../"

.\search.exe -F "F:\Tops_Sample\RP_104162_Military (1)\nexacroCom\typedefinition.xml" -K "../" --extract-pair "prefixid,url"
