# AI Policy for RMTC

April 1st 2026
 
The following document details the policies and procedures relating to responsible usage of AI in the development of RMTC.
 
## Context
 
RMTC is a provenance project developed with the intention of helping to protect creative rights in AI VFX pipelines - as a consequence, usage of AI code generation solutions to submit code to RMTC has to be undertaken with careful consideration. Rather than banning the use of such tools, and inviting undocumented and untraced adoption; we wish to create a policy around AI generative code. The policy aims to provide a framework for provenance and tracing at the development level - a goal inline with the aims of the project.
 
## Principles
 
- Human - someone is always in the loop
- Disclose - disclosure of AI use, where and how
- Responsibility - submitter takes full responsibility for PR in alignment with CLA
- Community - keep projects thriving, populated by people
- Graduated - phased adoption of AI
 
## AI usage definition
 
AI has been used for some time in software development, from code suggestions to spell checking. What does this policy cover?
 
### Examples of AI use (not exhaustive)
 
- AI generated source code, documentation, binaries, or text that is then included in a PR
- AI generated assets such as mesh, audio, video and images
- Agentic AI that act on behalf of a user
- LLMs or other modern statistical inference systems
- Derivatives of AI use - e.g. a generated image manipulated by hand, source code that is edited by a human
 
### Exclusions
 
- Using it to query, summarise or review the code but not generate an artifact for PR
- Spell checking
- Long standing inline code completion systems
 
## Human in the loop
 
Regardless of how the code was created - only humans can submit PRs. Only humans can review PRs. Only humans can commit them to the repository.

The intent is that a human must understand what is the submission and how it works - this precludes black box prompt only edits. There should be a trail of involkvement of a human in the creation of the submission - for excample, specifications, plans, updates to tickets or discussions on slack or similar sysytems.
 
PRs generated without an identifiable human author will be closed, we reserve the right to ban accounts if repeated or egregious violation of RMTC's poilicies as determined on a case by case basis.
 
## Disclosure
 
If AI was used to generate any artifacts checked into the repository, it is *mandatory* that the commit must disclose via 'Assisted-by' followed by the tool used and a brief description of what it was used for:
 
```Assisted-by: anthropic-claude-sonnet-4.6 - Generated tests for Model input processing```
 
Git hooks will be implemented to check as best we can for well formatted disclosures.

Why would we want to disclose?
 
* Project alignment - RMTC is a provenance system
* Provenance - users of RMTC may require knowledge of how RMTC was developed
* Reproducibility - we might want to repeat the generation process
* Exposure - educate each other on what works and share how best to use these tools
* Metrics - review which models are most effective and plan around their use
* Insurance - permit removal of code found to be infringing, permit creation of non-AI generated alternatives
 
## Responsibility & IP
 
To contribute to RMTC, a developer needs to abide by the [DCO](https://developercertificate.org/) and CLA, this is irrespective of the process by which the code was created - AI or otherwise. Anyone contributing a PR is ultimately responsible for the contents of that PR and responsible for any violations of RMTC's [LICENSE](../../LICENSE.md).
 
Not understanding the contents and deferring to AI is no defense for possible infringement. Avoid pure generative code - each line must be understood by the contributor and there ideally will be demonstrative evidence of that during discussion, or via supportive material (specifications or documentation).
 
## Community
 
Though you may use generative AI to generate code for your PR, you may not use agents or AI to communicate with the community or act on your behalf anonymously. You may not use agents or AI to submit the PR. This is to ensure we keep high levels of community engagement, to keep the quality level high for PRs and discourse and to keep the volume of PRs down to a manageable throughput for our reviewers.
 
First time issues for the project are not to be resolved using AI - they are for learning the project and are intended for education of new contributors. AI generated PRs for first time issues will be immediately closed.
 
## Graduated adoption
 
RMTC is an early stage project - it's code and community examples not yet established enough to allow for an AI to generate complementary code. Additionally, it is not clear regarding the possibility for reconstruction of license violating material for burgenoning projects which poses a specific issue for RMTC due to it's aims for responsible AI usage.
 
* Phase 0: No AI use of any kind
* Phase 1: No generative usage - limited to discovery and review
* Phase 2: AI use limited in scope to secondary artifacts - testing, documentation
* Phase 3: Minor bug fixes
* Phase 4: Major bug fixes, minor features
* Phase 5: Major features and refactoring
 
Definitions of minor, major bugs or features is at the discretion of the TSC and considered at the PR level.

Shifting from one phase to another requires a majority vote by the TSC.

RMTC is currently at Phase 1 - limited use for secondary artifacts and review
 
## Asset Generation
 
Asset generation of any kind ouside of text is banned - images, meshes, audio or any other kind of artistic asset. This is in direct contravention of the artist centric positioning of RMTC and is not required for the development of the platform.
 
## TSC rights reserved

The TSC reserves the right to alter any portions of this document, definitions or overall policy for RMTC with no warning or notification.

## References
 
- [OpenImageIO AI Policy](https://github.com/AcademySoftwareFoundation/OpenImageIO/blob/main/docs/dev/AI_Policy.md)
- [LLVM AI Tool Policy](https://llvm.org/docs/AIToolPolicy.html)
 
 
