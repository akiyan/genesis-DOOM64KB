# Genesis64KBDoom makefile
#
# 同梱(symlink) vendor/sgdk からネイティブビルドした libmd.a を用いてリンクする。
# GCC の既定 C23 と SGDK の typedef 衝突を避けるため EXTRA_FLAGS に -std=gnu11 を渡す。
#
# 使い方: ./build.sh  （PATH を整えてからこの makefile を呼ぶ）

GDK ?= $(CURDIR)/vendor/sgdk
EXTRA_FLAGS ?= -std=gnu11

include $(GDK)/makefile.gen
