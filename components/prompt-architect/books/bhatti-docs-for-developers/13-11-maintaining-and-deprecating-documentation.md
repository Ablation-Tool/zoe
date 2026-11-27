© The Author(s), under exclusive license to APress Media, LLC, part of Springer Nature 2021J. Bhatti et al.Docs for Developershttps://doi.org/10.1007/978-1-4842-7217-6_11
# 11. Maintaining and deprecating documentation

Jared Bhatti1, Zachary Sarah Corleissen2, Jen Lambourne3, David Nunez4 and Heidi Waterhouse5(1)Berkeley, CA, USA(2)Victoria, BC, Canada(3)Cornwall, UK(4)San Francisco, CA, USA(5)Mounds View, MN, USA
## Corg.ly: A few releases later

*Charlotte, Karthik, and their team had settled into a comfortable pattern with launching features and updating documentation. Charlotte focused on the audio translations created by Corg.ly, and Karthik on the video translations.*

*One afternoon, Karthik looked up from his computer and smiled. “Looks like we’re ready to move video translations out of beta!” he said.*

*“Excellent!” responded Charlotte, “When I ask Ein if he wants a walk, I’m never sure how urgent it is. Video helps a lot with that.”*

*“Walk?” Ein said, ears perking up.*

*Charlotte continued. “You mentioned this launch has some pretty big changes to the API as well, changes that will affect users.”*

“I know,” Karthik sighed. “How can we document API changes clearly so that Mei’s team isn’t caught off guard?”![../images/505277_1_En_11_Chapter/505277_1_En_11_Figa_HTML.jpg](/api/v2/epubs/urn:orm:book:9781484272176/files/images/505277_1_En_11_Chapter/505277_1_En_11_Figa_HTML.jpg)

*As Charlotte and Karthik outlined a few different ways to make changes and communicate them to their users, Ein interrupted them. With his leash held in his mouth, Ein barked.*

*“Walk now?” his translator asked.*

## Maintaining up-to-date documentation

Applications grow and evolve over time. Methods get rewritten. Products incorporate new technology. Teams add new features and deprecate and remove others. All of these changes affect your documentation.

Can you recall finding documentation about a product you were using, only to discover that the answers in the document weren’t correct anymore? You probably felt frustrated and annoyed. Too often, documentation is written and released once, with no subsequent updates. As the product gains new functionality, the documentation increasingly falls out of date, diverging from what the code actually does. The greater the gap between what the documentation says and what the code does, the more your users are frustrated and the less they trust your product.

As Karthik and Charlotte experienced, changes to the functionality and interface of your code affect the developers using your product. Documentation allows you to keep your readers informed of changes, improving your user’s experience by transitioning them to features and functionality that best addresses their needs while steering them away from deprecated features. Your documentation can also proactively answer questions that readers may have about your changes, giving readers the best, most up-to-date experience with your product.

This chapter guides you through maintaining your documentation alongside your code, including:- Planning for maintenance
- Helpful maintenance tools
- Deprecating and removing content when it’s no longer needed

This chapter’s strategies are designed to integrate with how you already release and maintain your code. You can take the guidance in this chapter and tweak it to work with your own development process.

## Planning for maintainability

Maintaining your documentation requires you to align writing your code with writing your docs. As you design new features, consider what updates need to happen to both your code and your content. If your new feature changes your API, or how your users interact with other parts of your application, you need to inform users through your documentation. Plan accordingly.

Start your plan by considering how your users are impacted and answering the following questions:- How are users impacted by this change?
- How does this change affect existing product functionality?
- What existing documentation does this change affect?
- What new documentation do we need to create to support our users?

These questions help you perform a user impact analysis, which is a shorter version of the user research done in Chapter [1](505277_1_En_1_Chapter.xhtml). A user impact analysis highlights how your users are affected by the change you’re proposing, and what documentation needs to be updated or created to address the situation.

Some changes, like code refactoring or optimizations, don’t need documentation changes at all—but the vast majority of feature changes require changes to your documentation as well. Small changes need updates to your existing reference documentation, but larger changes, like the one that Karthik proposed, need entirely new pages added to your documentation set.

By thinking about documentation early in the process, you can budget time accordingly and prevent your documentation from falling out of date when you update your code.

### Align documentation with release processes

Once you’ve budgeted time in your planning process for updating documentation, you should also integrate documentation into your release process. Updated documentation and code should be released at the same time, guaranteeing that they both stay in sync.

There are many ways you can align docs with a release. One way is to create tracking issues or bugs for each documentation update required for a release. Another way is to track documentation needs in a spreadsheet along with feature requests.

For example, Kubernetes (Kubernetes.io) tracks its feature release process using a spreadsheet. Kubernetes is an open source project for automating container deployment and management with over 43,000 contributors.1 Despite its large size and rotating group of contributors, Kubernetes aligns new feature releases (called “enhancements”) and documentation updates with the following release process:21. 1.A tracking spreadsheet lists all proposed enhancements for the upcoming release.
2. 2.Each proposed enhancement is documented in a Github Issue, and is required to have a design doc, feature owner, unit tests, and an assessment of whether or not documentation is necessary.
3. 3.If the enhancement needs documentation, the feature owner must open a Pull Request for documentation and receive approval before the enhancement is approved for release.
4. 4.Once the code, unit tests, and documentation are all approved for the enhancement, the enhancement is approved for launch.
5. 5.On the release date, all approved enhancements are pushed with the new release.

In the case of Kubernetes, the process for releasing code enhancements is tightly coupled with the documentation process. This effort keeps the documentation up to date, preventing the documentation from diverging from the code.

Release processes differ between companies, projects, and teams. The important thing is to find a process that works for you.

### Assign document owners

Documentation  often seems like a task that everyone is responsible for—and therefore *no one* is responsible for. Make responsibility clear with explicit assignments to owners who are responsible for responding to documentation issues, reviewing documentation changes, and updating documentation when needed. Clear, unambiguous responsibility helps prevent documentation from going out of date.

If your documentation is already in a source code repository, access to the revision history and identifying the last person who updated the documentation may be enough. However, for larger, more complex sets of documentation, it’s useful to assign specific documentation owners who own and understand how the larger set of documentation fits together.

Many source code repositories have an option for setting explicit code owners who are responsible for specific files or directories of content. For example, you can use CODEOWNERS files in Github to specific documentation owners.3 Alternatively, you can add comments or metadata to the top of your documentation and list the owners of your documentation, for example:<!-- Owners: Charlotte@corgly.com, Karthik@corgly.com -->
### Reward document maintenance

It’s important to reward the efforts of developers who create and review documentation, close documentation issues, and keep content up to date. Documentation is a lot of work! Recognition and rewards motivate developers to create and maintain good documentation.

Rewards and recognition for maintaining documents might include gift cards, thank-you notes, and public praise, depending on what motivates the person. It’s also important to be sure that your team is not penalized for taking time to do documentation. Writing and maintaining the docs should be built into performance expectations and debt estimates, not considered an “extra” or “bonus” task.

## Automating documentation maintenance

The goal of automating documentation work is to eliminate toil. Toil isn’t just “work you don’t like to do”; toil has a specific definition in the world of software engineering:4> *“Toil is the kind of work that tends to be manual, repetitive, automatable, tactical, devoid of enduring value, and that scales linearly as a service grows.”*

There are many opportunities to make documentation maintenance easier through thoughtful automation. The next sections show a few examples of eliminating toil through automation, including automating freshness checks, using documentation linters, and automating reference doc generation.

Be warned, however: while good automation saves people from toil, bad automation can compound toil into a crisis. Before you automate a process, be sure you understand all the steps and handoffs.

The tools you use to generate documentation depend heavily on how you’re publishing your content. Whichever tools you use, it’s good to search for places where you can automate your work and reduce the toil of maintenance. For more information on automation tools, see the Resources appendix.

### Content freshness checks

With a large enough documentation set, some documents eventually become stale and out of date. One way to avoid staleness is to show the “last modified” dates for your content on the rendered page. Last modified dates denote the last time that the document was reviewed or updated. If your documentation is stored in a source code repository, you can pull this information directly from your repo. Otherwise you can embed metadata in the document to store this information.

In addition to last modified dates, you can set times in the future to verify the contents of your document. For example, Google attaches metadata to the top of internal documents for freshness reminders. If the document isn’t updated in a set amount of time, for example six months, a reminder is sent to the document owner to review the document and verify that the content is still accurate. The metadata looks like this:5<!--Freshness: {owner: "karthik" reviewed: 2021-06-15}-->When document owners receive a notification to do a freshness check, they review the document to make sure the content is still accurate. The review date for the doc is updated, and the reminder is set for another six months. Google found that by using freshness checks, document owners were incentivized to keep their documentation up to date, and that documentation that uses freshness checks is more trustworthy.

### Link checkers

Links in your documentation can break when the link target is moved, archived, or deleted. As your documentation grows, verifying that all of your links work can be a frustrating, time consuming process. Link checkers relieve toil by verifying all the links in your site, flagging links that generate 404 errors for updates.

Link checkers work in one of two ways:- By running against your documentation prior to publication as part of your CI/CD toolchain
- By running against the documentation after it’s published by crawling your document like a web page

How you integrate a link checker into your documentation depends on the tools you’re using for publishing and hosting your documentation. There are multiple tools available for both approaches.

### Linters

Documentation linters , or prose linters, operate on the same principle as code linters. They can find, flag, and propose fixes to common issues found in documentation. Prose linters are similar to the spelling and grammar checker included with most word processors, such as when your spellchecker catches misspellings of common words.

Linters can also recognize and ignore text that is specific to your company. For example, “Corg.ly” is not a real word, and could be flagged as a misspelling of “corgi”, but that would be incredibly annoying for the employees who work there. Instead, you can add “Corg.ly” to the linter’s dictionary so that if someone types “Corg.ly”, the linter will suggest using the appropriate capital letter.

Some prose linters can be quite sophisticated and flag language choices that may seem exclusionary or hurtful. They can also catch issues where content doesn’t conform to your style guides or content templates.

Ultimately, linters are just exceedingly fancy regex expressions. They can’t help you with every prose or grammar problem, but they can catch many common issues and automate toilsome reviews .

### Reference doc generators

Reference documentation can be painstakingly difficult to maintain by hand. Automating reference doc generation significantly reduces your maintenance burden. It also produces more accurate documentation that’s easier to update.Automation tools can be built from scratch for simple automation tasks. For larger tasks, like API documentation, there are a host of tools you can use. OpenAPI and Javadoc are good examples of tools for generating API documentation and formatting the output into templates.

## Removing content from your docset

Content grows and evolves over time. Even if you keep documentation closely aligned with code releases, it’s possible for documentation to become stale or obsolete. Sections of a document might no longer be relevant to your users, or an entire document might no longer be necessary due to changes in your API or service. Deprecating content notifies your users that they should no longer use this feature or service.

It’s important to know when to deprecate content so you’re not presenting incorrect information to your users. Once content is deprecated and users are notified, you can delete the content. It's also important to remove content correctly so users aren’t stranded when you delete information from your site.

### Deprecating documentation

Deprecation, in the programming sense, is the process of marking older code as no longer useful, usually because it’s been superseded by newer code in a codebase. For instance, you might deprecate parts of your API because you released a new version of your API that you want developers to use instead. Developers who see code flagged as deprecated know it will be removed at a future date, so they should both steer clear of using it for anything new and plan to migrate existing features away.

Documentation should be deprecated in a similar manner. You might be tempted to hide the features that you’re deprecating, but it’s critical that your users know if something they’re relying on is going to go away. Imagine their frustration if their product unexpectedly breaks because they relied on code they thought was still maintained!

Documentation plays an important role in informing your users of feature deprecations. If specific features or code are deprecated, the documentation associated with that code should have callouts that notify developers to avoid using that feature. If there are newer alternatives to the deprecated code that developers should use instead, callouts should link to that new feature as shown here:

DeprecatedThe Corg.ly Audio API was deprecated on August 20, 2021. It has been replaced by the Corg.ly Multimedia API, which supports both audio and video.

You should also consider additional ways of notifying your users of upcoming deprecations. One way is to list deprecated features in release announcements or release notes. Another option, if you have a lot of deprecations in your codebase, is to create a page in your documentation that contains a list of deprecations that’s updated with each release of your software.

Depending on how much a deprecated feature impacts your users, you should consider writing a migration guide to help users move off the soon-to-be-deleted feature. A migration guide can significantly reduce support issues and customer frustration. If you decide to write a migration guide, make sure to publish the guide before you announce the deprecation, so your users understand their path forward.

### Deleting documentation

As a rule, documentation should be deleted when it’s no longer useful to your users. There are a few common reasons this might happen. One is when all the users of a deprecated feature have successfully migrated away from it, the feature is being removed, and the documentation is no longer needed. Another reason to delete is when a piece of documentation is outdated or irrelevant and it’s not worth the time to fix it.

You might feel sad to delete content you’ve written, but the end goal is to help your users. Removing outdated and unnecessary content helps your users find the right information quickly without being distracted by documentation that is no longer useful or relevant. Your users will appreciate that you’re keeping your content tidy and focused by deleting content that’s no longer necessary.

If you’re deleting content because a feature is being removed, make sure to give your users adequate notice. Before shutting down the feature and deleting the documentation, document that the feature has been turned off in any product announcements or release notes, and update any links that point to the document that you are deleting.

If you are considering deleting a document because you think it’s no longer relevant to your users, you can use user feedback (Chapter [8](505277_1_En_8_Chapter.xhtml)) and document analytics (Chapter [9](505277_1_En_9_Chapter.xhtml)) to evaluate the content. If a particular page has a very low number of page views, and a large number of issues filed against it, it might be worth deleting the content instead of trying to fix it.

For example, let’s say Karthik writes two tutorials for translating dog barks with Corg.ly, one for audio files and one for video files. Each tutorial has extensive code samples that need a lot of maintenance. The video feature becomes wildly popular, and the tutorial is one of the most popular pages on the Corg.ly site. The audio feature isn’t used very often, and it doesn’t get many page views. In addition, the code samples for the audio page are out of date, and users are filing issues against the page.

Although Corg.ly continues to support audio translation, Karthik decides to delete the audio tutorial to prevent user frustration, and instead, points users to a much shorter, easier to maintain document on how to translate audio with Corg.ly.

## Summary

Make documentation maintenance easier by doing the following:- Plan code and documentation together with maintainability in mind.
- Align documentation releases with feature releases.
- Assign owners to documents.
- Automate toil with content freshness checks, link checkers, documentation linters, and reference doc generators—but be careful before automating.

Deprecate and delete documentation to keep your content up to date and useful. Inform users about deprecations and deletions through callouts, release notes, and announcements, and set up redirects to prevent users from being stranded when content moves or you delete it.

The next sections cover when to hire an expert and additional resources for creating developer documentation.

Footnotes1“How Kubernetes contributors are building a better communication process”, Paris Pittman, Kubernetes Blog, published 21 April, 2020, [https://kubernetes.io/blog/2020/04/21/contributor-communication](https://kubernetes.io/blog/2020/04/21/contributor-communication).

2“Documenting a feature for a release”, Kubernetes documentation, last modified 11 February 11, 2021, Retrieved from: [https://kubernetes.io/docs/contribute/new-content/new-features/](https://kubernetes.io/docs/contribute/new-content/new-features/).

3“About Code Owners”, GitHub, accessed 29 December 2020, [https://docs.github.com/en/free-pro-team@latest/github/creating-cloning-and-archiving-repositories/about-code-owners](https://docs.github.com/en/free-pro-team%2540latest/github/creating-cloning-and-archiving-repositories/about-code-owners).

4Betsy Beyer, Chris Jones, Jennifer Petoff, and Niall Richard Murphy, *Site Reliability Engineering: How Google Runs Production Systems 1st. ed.*, (O’Reilly, 2016).

5Titus Winters, Tom Manshreck, Hyrum Wright, “Documentation” in *Software Engineering at Google: Lessons Learned from Programming over Time*, (O’Reilly, 2020).
