include $(TOPDIR)/rules.mk

PKG_NAME:=f50-ra-refresh
PKG_VERSION:=0.1.1
PKG_RELEASE:=1
PKG_LICENSE:=MIT
PKG_MAINTAINER:=JasonBeam

include $(INCLUDE_DIR)/package.mk

define Package/f50-ra-refresh
  SECTION:=net
  CATEGORY:=Network
  TITLE:=Conservative IPv6 RA refresh for cellular WAN
  DEPENDS:=+ip-full +flock +jsonfilter +ubus +uci
  PKGARCH:=all
endef

define Package/f50-ra-refresh/description
Requests a genuine Router Advertisement when its lifetime is low.
Never deletes routes or restarts networking. Requires a trusted rdisc6 tool.
Disabled until explicitly configured.
endef

define Package/f50-ra-refresh/conffiles
/etc/config/f50_ra
endef

define Build/Compile
endef

define Package/f50-ra-refresh/install
	$(CP) ./root/* $(1)/
	chmod 0755 $(1)/usr/sbin/f50-ra-refresh $(1)/etc/init.d/f50-ra-refresh $(1)/usr/libexec/rpcd/f50.ra
endef

$(eval $(call BuildPackage,f50-ra-refresh))
