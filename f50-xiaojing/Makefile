include $(TOPDIR)/rules.mk

PKG_NAME:=f50-xiaojing
PKG_VERSION:=0.1.0
PKG_RELEASE:=1
PKG_LICENSE:=MIT
PKG_MAINTAINER:=JasonBeam

include $(INCLUDE_DIR)/package.mk

define Package/f50-xiaojing
  SECTION:=net
  CATEGORY:=Network
  TITLE:=Xiaojing IoT traffic-pool calibration
  DEPENDS:=+ruby +ruby-json +curl +ca-bundle +ubus
  PKGARCH:=all
endef

define Package/f50-xiaojing/description
Calibrates the MU300 unisoc.traffic ledger against the Xiaojing portal.
Disabled by default. Credentials stay in a private backend-only JSON file.
endef

define Package/f50-xiaojing/conffiles
/etc/f50-xiaojing/config.json
endef

define Build/Compile
endef

define Package/f50-xiaojing/install
	$(CP) ./root/* $(1)/
	$(INSTALL_DIR) $(1)/etc/f50-xiaojing
	$(INSTALL_CONF) ./root/etc/f50-xiaojing/config.json.example $(1)/etc/f50-xiaojing/config.json
	chmod 0700 $(1)/etc/f50-xiaojing
	chmod 0600 $(1)/etc/f50-xiaojing/config.json
	chmod 0755 $(1)/etc/init.d/f50-xiaojing $(1)/usr/libexec/f50-xiaojing $(1)/usr/libexec/rpcd/f50.xiaojing
endef

$(eval $(call BuildPackage,f50-xiaojing))
