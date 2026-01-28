<!-- SPDX-License-Identifier: CC-BY-4.0 -->
<!-- Copyright Copyright Contributors to the RMTC Project -->

# Release Process for RMTC

The following assumes that the current RMTC framework version number is 6.0.0 and the new version number is 6.1.0. Adjust for the actual version numbers as appropriate.

- [ ] Open a ticketing system ticket "Release RMTC 6.1.0" ticket with "RMTC_6.1.0" as the Fix Version.
- [ ] Update `CHANGES` with release notes.  (A project may want to adopt automated tools for release notes management / generation).
- [ ] Open a pull request to merge the above changes into `RMTC/main`.  Associate the pull request with the ticketing system ticket created earlier, and verify that the CI build runs successfully.
- [ ] Draft a new GitHub release. Title it "RMTC 6.1.0" and tag it as `v6.1.0`.
- [ ] (When applicable) Update front page of project web site with a news item announcing the release, and delete the oldest news item.  Open that page in a browser and check that the website renders correctly and that there are no broken links.
- [ ] Build the auto-generated documentation with the appropriate build system targets and replace the contents of the project website documentation directory with the output.
- [ ] Open a pull request to merge the above changes into the website repository.  Associate the pull request with the ticketing system ticket created earlier.
- [ ] Post a release announcement to the RMTC public announcement slack channel
- [ ] (If applicable) In preparation for the next release, change the correct #define in the project's base version include file.  Unless it is known that the next release will include API- or ABI-breaking changes, increment only the patch number to begin with (in this case, from 6.1.0 to 6.1.1).  Update any references to the project version number in the documentation source files, and add a "Version 6.1.1 - In development" section to the `CHANGES` release notes file.  Open a pull request to merge these changes into `PROJECT/main`.
- [ ] Add a "RMTC_6.1.1" version to the ticketing system.

