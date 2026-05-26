# Dockerfile (Alpine Linux Lite)
# Stage 1: Build and customize the rootfs for development (Lite - Alpine Linux)
ARG TARGETPLATFORM
FROM alpine:3.23 AS customizer

# Install key packages
RUN apk update && apk upgrade && \
    apk add \
    # Core utilities
    curl \
    wget \
    ca-certificates \
    zstd \
    tzdata \
    shadow \
    # Networking
    iptables-legacy \
    # DHCP client + openrc
    openrc \
    busybox-extras \
    # SSH
    dropbear \
    # FTP
    vsftpd \
    # 内存分配器
    jemalloc \
    mimalloc \
    && rm -rf /var/cache/apk/*

# Copy custom scripts
COPY scripts/bashrc.sh /etc/profile.d/ds-aliases.sh

# Make scripts executable
RUN chmod +x /etc/profile.d/ds-aliases.sh

# Apply Android compatibility fixes
RUN <<EOF_RUN
# --- 1. General Fixes ---
# Android network group setup (required for socket access on Android kernels)
grep -q '^aid_inet:' /etc/group    || echo 'aid_inet:x:3003:'    >> /etc/group
grep -q '^aid_net_raw:' /etc/group || echo 'aid_net_raw:x:3004:' >> /etc/group
grep -q '^aid_net_admin:' /etc/group || echo 'aid_net_admin:x:3005:' >> /etc/group

# Root permissions for Android hardware access
usermod -a -G aid_inet,aid_net_raw,input,video,tty root || true

# Configure legacy iptables (MANDATORY for Android compatibility)
ln -sf /usr/sbin/iptables-legacy /usr/sbin/iptables && \
ln -sf /usr/sbin/ip6tables-legacy /usr/sbin/ip6tables && \
ln -sf /usr/sbin/arptables-legacy /usr/sbin/arptables && \
ln -sf /usr/sbin/ebtables-legacy /usr/sbin/ebtables && \
ln -sf /usr/sbin/iptables-legacy /sbin/iptables && \
ln -sf /usr/sbin/ip6tables-legacy /sbin/ip6tables && \
ln -sf /usr/sbin/arptables-legacy /sbin/arptables && \
ln -sf /usr/sbin/ebtables-legacy /sbin/ebtables

# Tell OpenRC it's in an LXC-style container.
# This suppresses the hwdrivers/machine-id "needs dev" warnings without
# disabling anything useful. In hw-access mode, devtmpfs/sys are mounted
# by Droidspaces before init runs, so OpenRC never tries to manage them
# anyway - rc_sys="lxc" just stops it from complaining about their absence.
sed -i 's/^#\?rc_sys=.*/rc_sys="lxc"/' /etc/rc.conf


# Remove "dev" dependency from machine-id init script to prevent boot warnings
if [ -f /etc/init.d/machine-id ]; then
    sed -i 's/need root dev/need root/' /etc/init.d/machine-id
fi

# Fix inittab:
# 1. Remove useless tty1-6 (no VTs in a container)
# 2. Add console getty for the Droidspaces foreground console
# 3. Add console to securetty so root login is allowed
sed -i '/^tty[1-6]::/d' /etc/inittab
grep -q 'console::respawn' /etc/inittab || \
    echo 'console::respawn:/sbin/getty 38400 console' >> /etc/inittab
grep -q '^console$' /etc/securetty || echo 'console' >> /etc/securetty

# networking
echo -e "auto eth0\niface eth0 inet dhcp" > /etc/network/interfaces
mkdir -p /etc/runlevels/default
ln -sf /etc/init.d/networking /etc/runlevels/default/networking

# nat network
sed -i '/start()/i start_pre() {\n\tif ! grep -q "net_mode=nat" /run/droidspaces/container.config 2>/dev/null; then\n\t\teinfo "Skipping native networking: not in NAT network mode"\n\t\treturn 1\n\tfi\n}\n' /etc/init.d/networking

# Mark fixes as completed
echo "Post-extraction fixes applied on $(date)" > /etc/droidspaces


# FTP vsftpd
mkdir -p /etc/vsftpd
cat << 'EOF' > /etc/vsftpd/vsftpd.conf
anonymous_enable=NO
local_enable=YES
write_enable=YES
force_dot_files=YES
file_open_mode=0777
local_umask=022
dirmessage_enable=YES
xferlog_enable=NO
connect_from_port_20=YES
trans_chunk_size=131072
listen=YES
listen_port=21
EOF
ln -sf /etc/init.d/vsftpd /etc/runlevels/default/vsftpd

# SSH
ln -sf /etc/init.d/dropbear /etc/runlevels/default/dropbear

EOF_RUN

# Final cleanup
RUN rm -rf /var/cache/apk/*

# Stage 2: Export to scratch for extraction
FROM scratch AS export

# Copy the entire filesystem from the customizer stage
COPY --from=customizer / /
