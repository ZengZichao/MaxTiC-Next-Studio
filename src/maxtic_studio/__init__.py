"""MaxTiC-Next Studio —— 独立桌面端（PySide6）。

与命令行核心 ``MaxTiC-Next`` 共享算法（``maxtic_next.api.rank``），
但作为**独立仓库/独立发行物**存在：本包只依赖已安装的 ``MaxTiC-Next``，
不再被核心包反向引用。

安装::

    pip install "git+https://github.com/ZengZichao/MaxTiC-Next.git"   # 先装核心仓库 MaxTiC-Next
    pip install .                     # 再装 Studio

启动::

    maxtic-studio
"""

__version__ = "0.1.0"

__all__ = ["__version__"]
