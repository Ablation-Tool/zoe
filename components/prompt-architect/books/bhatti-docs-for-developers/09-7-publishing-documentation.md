© The Author(s), under exclusive license to APress Media, LLC, part of Springer Nature 2021J. Bhatti et al.Docs for Developershttps://doi.org/10.1007/978-1-4842-7217-6_7
# 7. Publishing documentation

Jared Bhatti1, Zachary Sarah Corleissen2, Jen Lambourne3, David Nunez4 and Heidi Waterhouse5(1)Berkeley, CA, USA(2)Victoria, BC, Canada(3)Cornwall, UK(4)San Francisco, CA, USA(5)Mounds View, MN, USA
## Corg.ly: Ship it!

*Feeling a sense of anticipation, Charlotte took one final look through her documentation. Thanks to Karthik’s help, the documentation had pulled together faster than she’d expected. She scanned through the document, looking over the code samples and diagrams to make sure everything looked right. It’s ready, she thought.*

*The next step was putting the documentation in front of developers. She could email a copy to Mei so Mei’s team could get started, of course, but email wasn’t going to scale to the thousands of developers she hoped to attract to Corg.ly. She needed to publish it online, but where?*

*She messaged Karthik. “I want to run something by you real quick. I’m debating where to publish this documentation, and there are a couple of different ways I can do this.”*

*“Of course,” Karthik replied. “What are you thinking?”*

![../images/505277_1_En_7_Chapter/505277_1_En_7_Figa_HTML.jpg](/api/v2/epubs/urn:orm:book:9781484272176/files/images/505277_1_En_7_Chapter/505277_1_En_7_Figa_HTML.jpg)

*Charlotte walked through a few different places they could publish the content and a few different tools they could use to manage publication. In the end, they narrowed down the process to the simplest solution available: adding the documentation to a new section on their company website and managing content with the same version control system they used for their code.*

*“I can also write up a quick post for our company blog,” Karthik suggested. “Everyone will know when it’s up and where to find it.”*

*“That sounds great,” Charlotte smiled. “I’m ready to celebrate once this is live for everyone to see.”*

## Putting your content out there

Publishing content used to be a clear process. You sent your proofs to the printer, complete with registration marks and ink numbers, and several weeks later you got back documentation in the form of printed manuals. From there, you had to ship physical copies into the hands of your readers.

We don’t live in that world anymore. Nowadays, publishing means making content available to read and follow, similar to announcing that a piece of software has been released. What we mean by “publishing” now is usually “making your content available electronically to the intended audience.”

Sometimes it’s emotionally difficult to publish something: once it’s out in the world, people will have reactions to it. It’s easy to fall into the trap of having “just a few more things to fix” and never actually getting a document out to readers. You might worry that people will judge it harshly, that it’s incomplete, or that you’ve forgotten or missed something and therefore want to stall its release.

Relax: like code, almost no document is perfect at release. The best way to handle your fears about publication is to publish and then iterate based on feedback. It’s okay to patch your documents, to update them, to modify them after they have been published—just like it’s okay and even expected that you’ll patch and update your software. Publishing is no longer a printed artifact, just like a software release is no longer a CD.

There are a myriad of tools and locations to choose from. Publishing your documentation can mean creating a website, a blog post, a GitHub gist, or an internally facing wiki. To help you navigate the publishing process, this chapter guides you through some of the decisions you’ll need to make, including:- Building a content release process
- Creating a publishing timeline
- Finalizing and approving publication
- Announcing your content to your audience

## Building a content release process

Just like your organization (hopefully!) has a software release process, you should also build a release process for your documentation. Your content release process is the plan for publishing your content. It contains the timeline for publishing, assigning responsibilities for final content review and publication, and designating where to publish content.

Your content release process should answer the following questions:- When are you going to publish your content?
- Who is responsible for final review and publication?
- Where are you going to publish your content?
- What additional software tools are needed to publish the content?
- How will you announce your new content to your users?

A content release process can be as lightweight as a checklist, or it could be a fully scripted integration with your existing software release process. What’s important is that you have a plan for getting your content to your audience.

You should customize your content release process for the size of your launch. For example, for this initial release of Corg.ly, Charlotte has a fully planned release, complete with a timeline for software and content publishing, final reviewers for content, and a blog post announcement to inform Corg.ly’s users about the upcoming release. However, if Karthik fixes a small bug and it isn’t part of a major release, a single peer review can suffice for a brief update.

## Creating a publishing timeline

A publishing timeline is a way to make sure that all the essential tasks of publishing are included and that you have enough time to complete them. Doing user researching, creating a documentation plan, drafting documentation and getting reviews all takes time. A Gantt chart is a useful way to represent the planning that goes into a full release (Figure 7-1). For example, if you need three days for the web team to verify and upload something, two days to incorporate feedback, and one week to edit, you can see that you need to have the draft ready for editing two weeks before your publication target.![../images/505277_1_En_7_Chapter/505277_1_En_7_Fig1_HTML.jpg](/api/v2/epubs/urn:orm:book:9781484272176/files/images/505277_1_En_7_Chapter/505277_1_En_7_Fig1_HTML.jpg)

*Figure 7-1A Gantt chart  with a publishing timeline*

When setting your publishing timeline, it’s useful to make sure you’re aligned with the software release and other relevant events. Projects used to have time set aside for independent QA cycles, and so did documentation—but in a faster, more agile development world, you don’t have that luxury. Instead, you need to build your publishing timeline into the rest of your release timeline and make sure the teams responsible know that they need to hold time for essential writing and review.

A publishing timeline created with buy-in from other release stakeholders is a great way to align schedules and uncover potential problems before they affect a release schedule. A publishing timeline also clearly defines the owners for each part of the process.

Set a publishing timeline for all your documentation releases. Even small or light releases need some participation from others.

### Coordinate with code releases

Developer documentation needs to release with the software it’s describing. There is no amount of training or user interface design that can cover up missing documentation. Coordinating a publishing schedule with the product release schedule allows everyone to understand that this is all the same release and needs to go out together.

If you’re doing a small documentation release, you may not need a full publication cycle. Notify users of documentation changes and updates in the release notes.

### Finalize and approve publication

You should assign a single, final approver who is responsible for allowing or halting a documentation release. This approver should be listed in the publishing timeline, and they should have final say in the amount of content and its level of quality before you launch. No document is ever going to be perfect, but no released document should be harmful. Be sure you have a responsible party for that decision.

This person should also be responsible for testing and reviewing the documentation prior to the release. If this person is you, then you will probably find some errors. When you discover errors, decide in advance what your criteria are for stalling a release. You can use the same triage system for documentation bugs that you use for code. Will it cause harm to people? Damage to systems or software? Data loss? Most documentation doesn’t have the ability to go that wrong, but neither does most software, and most organizations still have a triage category for it.

If your organization wouldn’t release code without a peer review and some automated testing, you shouldn’t release your documents that way, either. The simplest way to ensure parity would be to use your code review process for documentation. If it’s going to be part of your codebase, it certainly needs to pass all the integration tests that your code does. If you have a culture of peer review or QA, your docs should be held to the same standard.

Test your docs, even if they’re not part of your codebase. If you don’t have unit tests for code samples, test instructions manually. For example, does following a procedure produce the expected outcome for users? Remember that when you write a procedure, you know more about it than most users, and that knowledge may lead you to skip “obvious” steps that not everyone knows. For example, you may write$ brew install --cask firefoxas an instruction, but for that to work, the user has to be using MacOS, have Homebrew installed, and be typing at the command line with sufficient permissions. Your user may know that, or they may not; that’s why audience analysis is so important.

It’s safer to err on the side of overexplaining, but make sure your instructions don’t become too big or unapproachable for both readers and writers. Think of instructions for making a sandwich that start with how to remove the fastener on a bag of bread: that level of detail might be necessary for some readers, but is too much for most. If you try to write for every user, you may alienate readers in your most important use cases. For purposes of testing, make sure your target user can perform the action you describe with the information you provide or can reasonably expect them to have.

Now is also a good time to decide on criteria for stopping a release. If something isn’t quite ideal, or maybe a little awkward, it’s probably not worth slipping your publication date. If something is materially wrong and may cause harm, you need to stop publication until it’s fixed. Set your standards and stick to them. This sounds simple, but there will be judgment calls, which is why defining your standards in advance helps.

### Decide how to deliver content

If you’re adding content to a site that already exists, then most of these decisions will be made for you. However, if you’re publishing new content, you should give careful thought to where it will live and how your users will find it.

When deciding where to publish your content, it’s important to remember the following rule:> *Meet your users where they are.*

Your publishing destination depends on how your readers want to experience the content. To meet your users where they are, consider the following questions and scenarios:- Are they internal teams looking for the right way to use something in your organization? A private wiki or an intranet site is a good place to put it.
- Are your readers external users who work with code or endpoints? It’s convenient for them if the documentation is in the same repository as the code.
- Are your readers end users or system administrators looking to install something? Make sure the documents are external to the software to avoid a dependency loop.
- Are your readers external users of your codebase? Put it on your website or in your code repository.

Based on your audience research, you probably have an idea of how your audience is expecting to use your documentation. If you’re putting your documentation somewhere it will be indexed, be sure that the headings are clear and that you allow search indexing. It’s disappointing to put effort into documentation only to realize that no one is reading it because they can’t find it.

Also, if it’s your first time publishing to a new location and you’re using a new set of tools to do it, try manually publishing a test document to your destination in advance. Take notes on the gaps you find in tools or understanding. That’s right: your documentation needs documentation, or at least the process for releasing it does. Running a test document through your publication process means that when you upload the full set of documentation, you can be sure it arrives intact, and so others can follow the process too.

### Announce your docs

After your documentation goes live, it’s important to announce to your readers that it’s available. For documentation aligned with a release, it’s easy to link to the technical documentation anywhere you make the announcement for the new release.

If you’re launching a whole set of documentation, then link to the most logical entry point for your readers. For example, for the upcoming Corg.ly release, Charlotte could point new users to the new “Getting Started” page for Corg.ly. This would be the most logical entry point for new users.

You can also bundle announcements about new documentation into emails that go to your users or with release notes and in-application notifications. The important thing is to let people know there is a new resource available.

## Planning for the future

Your documents are living documents, just like your code. You need to have some plans for what will happen to them.

Developers often spend time on call (“pager duty”) for critical responses. It may surprise you to learn that documentation can also require critical response. There are some industries and products where documentation errors are incident-worthy problems and people get paged about them. If your documentation is critical, then you need to plan for critical response, with a runbook, just like you would have for any operations problem.

How often do you update your documentation? If your content is tied to releases, you should make updates at the same cadence, even if it delays publishing some content. If your deployments are more continuous, then set predictable dates for documentation updates, and let your readers know about them in advance. Setting a schedule for your documentation updates also keeps these issues from sliding to the bottom of everyone’s priority list until you have a bunch of technical debt to work through.

Once you know your publication cadence and you’ve used your release process a few times, take a step back and look for places where you can improve the process. You might be tempted to use tooling and scripts to automate your publishing process initially, but it’s better to start with the least-complicated process that works and iterate on it. You can’t automate toil away until you understand where toil exists. Finding your actual friction points saves you much more time than guessing at them in advance of experience.

More information on maintaining content and content automation is in Chapter [11](505277_1_En_11_Chapter.xhtml).

## Summary

Create a documentation release process that aligns with your software release process. The release process should contain the timeline for publishing, assign responsibilities for final content review and publication, and designate where to publish content.

Assign a single, final approver who is responsible for allowing or stopping a documentation release. List this approver in the publishing timeline.

Test documentation before release. Verify that documentation is accurate, code samples work and are adequately described, and that content meets the bar for publication.

After your documentation goes live, announce its availability through channels such as product announcements, blog posts, customer emails, or release notes.

Iterate and improve your release process with better planning, communication, and tooling.
