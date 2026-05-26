# 关于

fork from https://github.com/Droidspaces/Droidspaces-rootfs-builder

此仓库为自用 Droidspaces Alpine/Debian13 Rootfs构建

默认启用了极简的FTP(21)方便在MT管理器管理文件，开机自行 `echo "root:密码" | chpasswd` 修改密码即可(用这个登录FTP即可)

Droidspaces已经带终端了，若还需SSH自行安装，推荐轻量的dropbear(本地无需考虑安全)，账号密码同上。

# Alpine

1.精简软件包安装

2.删除dhcpcd、ssh相关

# Debian13

1.精简软件包安装

2.删除ssh相关

3.删除amd64额外支持
