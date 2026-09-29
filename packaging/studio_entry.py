"""PyInstaller 冻结入口：转发到 ``maxtic_studio.main:main``。

spec 文件（``maxtic_studio.spec``）的 Analysis 以本脚本为入口；
不要在仓库其他位置直接运行它。
"""

from maxtic_studio.main import main

if __name__ == "__main__":
    main()
