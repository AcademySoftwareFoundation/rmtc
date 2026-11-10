<!-- SPDX-License-Identifier: CC-BY-4.0 -->
<!-- Copyright Copyright Contributors to the RMTC Project -->

# Deprecation & Lifetime Strategy for RMTC

Currently there are no major versions of RMTC supported so deprecation and lifetime strategy is to be confirmed by TSC members.

RMTC does support some basic deprecation functionality:
* Properties
* Whitelisted module entries

This functionality will be extended so all major systems can be versioned and deprecated. In general once deprecated they will be removed in the next major release of the library.

With regards to the VFX Reference platform, RMTC will be updated to support the last 2 versions of the platform - this may or may not increase the major revision number, if any breaking changes are required. 

For DCC integrations we expect to support the last 2 major releases of a DCC or as far back as the supported versions of the VFX Platform - whichever is earlier.

Guarantees on API compatibility will only stretch back 1 major version - this may be extended as per TSC direction.

If a serious security issue is found then that version may be patched.