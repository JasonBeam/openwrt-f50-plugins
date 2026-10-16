# Changelog

All notable changes are documented here using [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versions follow [Semantic Versioning](https://semver.org/); 0.x releases are experimental.

## [0.1.1] - 2026-10-16

### Added
- Added adaptive RA lifetime observation and sampled renewal intervals, with unknown values kept explicit.
- Added an adaptive-mode switch and LuCI status for learned lifetimes and renewal results; fixed-mode settings remain available.

### Fixed
- Verify actual route renewal after router solicitation instead of trusting the tool exit code alone.
- Discard learning across boot, interface or gateway changes and exclude this script's solicited responses from natural-cadence samples.

## [0.1.0] - 2026-10-16

### Added
- Added independent IPv6 RA refresh and Xiaojing IoT calibration source packages.
- Added optional LuCI interfaces, disabled defaults, installation guidance and isolated checks.
- Added versioned Release downloads, SHA-256 checksums, a release workflow and contributor guidance.

[0.1.0]: https://github.com/JasonBeam/openwrt-f50-plugins/releases/tag/v0.1.0

[0.1.1]: https://github.com/JasonBeam/openwrt-f50-plugins/compare/v0.1.0...v0.1.1
