© The Author(s), under exclusive license to APress Media, LLC, part of Springer Nature 2021J. Bhatti et al.Docs for Developershttps://doi.org/10.1007/978-1-4842-7217-6_2
# 2. Planning your documentation

Jared Bhatti1, Zachary Sarah Corleissen2, Jen Lambourne3, David Nunez4 and Heidi Waterhouse5(1)Berkeley, CA, USA(2)Victoria, BC, Canada(3)Cornwall, UK(4)San Francisco, CA, USA(5)Mounds View, MN, USA
## Corg.ly: Creating a plan

*Charlotte had spent the previous three weeks researching Corg.ly’s users. She and Ein did a few demos of the product at a local dog park with several interested initial users. She’d gotten to know how they wanted to use Corg.ly, the kinds of products and apps they wanted to build, and what they wanted from the documentation.*

![../images/505277_1_En_2_Chapter/505277_1_En_2_Figa_HTML.jpg](/api/v2/epubs/urn:orm:book:9781484272176/files/images/505277_1_En_2_Chapter/505277_1_En_2_Figa_HTML.jpg)

*She felt she knew their problems inside and out and how Corg.ly could solve them—but it was overwhelming to think of how to translate the information from her head into the right kind of documentation.*

*As Charlotte and Karthik thought about how to shape their* *documentation* *, they realized they could use the same approach: understand the users’ needs and shape the content to solve their use cases.*

*Charlotte’s team understood that new developers were their key users and that the getting started documentation was critical. In addition, a service with so many features meant they needed a strong set of use cases for the most common workflows. Also, because their service was still new, the team wanted to provide a safety net for new users with good troubleshooting content. Luckily, they already had existing resources like friction logs, user interviews, and meeting notes they could use as source material.*

*Knowing what they needed to deliver to users, it was time to actually plan the documentation.*

## Plans and patterns

In the previous chapter, you built a strong understanding of your audience through user research. With this understanding, you can decide which types of content to create to serve your users’ needs.

By the end of this chapter, you will know how to plan your documentation. You will also understand some different content types and how to determine which types best fit your users’ needs.

C*ontent types*  are different patterns for building effective and consistent documentation. Different content types help solve different kinds of problems.

This chapter explains the most common content types, when to use them, and which jobs require multiple types. This chapter also describes how to turn user research and the existing content you have (design documents, emails, whiteboard sessions, meeting notes, old documentation, and rough drafts) into a plan for your documentation. Your plan will guide what you write and how you write it.

A *use case*  (also called a business problem or user scenario) is a set of tasks required to complete a goal. Each task is an interaction with your service or systems. You can create use cases from researching your users and finding what goals are most important to them. When you identify the most important use cases for your users, you can plan your documentation with content types that address their needs. Good documentation describes use cases that help your users meet their goals.

By the end of this chapter, you will:- Understand the common content types for developer documentation
- Learn about the patterns that best support each content type
- Learn how certain content types best complement each other
- Build a comprehensive plan for creating your content

## Content types

Content types help you write the specific kinds of documentation your users need. Each document type serves a specific task, user archetype, or learning preference.

The following section describes the most common content types for developers and shows you how to assemble them into a documentation plan. Although each of these content types has its own templates and guidance, you should shape them into what works best for your users.

### Code comments

The most basic content type for developers is code comments . Beyond describing what your code does, code comments document design decisions and tradeoffs made when writing code, describing what you did and why you did it.

The tenets for good code comments are to:1- Keep them brief
- Make them relevant
- Use them liberally, but not excessively

As a code base evolves, it’s useful to preserve the context for past decisions, and a single inline code comment before a particularly complex piece of code can save future developers a lot of time. Code will never be perfect, especially in complex services, and therefore it’s rarely self-documenting. You may eventually have more people looking at your code, whether it’s a colleague doing support, a new engineer on your team, or, if you’re contributing open source code, an entire community.

Some developers  advocate against code comments, promoting the idea that your code should be so clear that code comments are unnecessary. They also suggest that code comments are a maintenance burden, with comments having to be updated when the code is updated. This argument makes a certain amount of sense. However, code comments reduce confusion and ambiguity about what your code does and provide useful context and information that doesn’t exist in the code itself.

NoteEven as a solitary developer working on a project, code comments can be a tremendous help. If you’ve put code aside and returned to it after weeks or months, you may have experienced bewilderment at what you were doing or why you made certain choices. Comments help you reorient to your own code.

### READMEs

Code comments alone aren’t enough to help your users understand a system at a summary level. To help users understand why your code exists—the problems your code solves and why it matters—you can write a README.

A README is a single text file, often written in Markdown, that summarizes a collection of code, usually at the top level of the code repository.2 You can also write READMEs for important subfolders that require additional summary or explanation. A README contains basic information like:- What the code does at a high level
- How to install it
- Troubleshooting steps
- Who maintains the code
- License information
- A changelog
- Basic examples
- Links to more in-depth resources and documentation

Listing 2-1 provides a README template.

ReadmeA paragraph or two that encapsulates what the code does at a high level. For example: Corg.ly is a service that translates dog barks into human language. Corg.ly uses an API to send and receive translations, and uses a machine learning model to regularly improve its translations.

**## Installation**

1.

2.

3.

4.

5.

**## Examples**

**## Troubleshooting**

**## Changelog**

**## Additional resources**

**## License information**

A README needs to be concise, informative, accurate, and up to date. As you continue working on code, make sure to keep the README current with the changes you make. Along with serving as a cheat sheet for the code repository, a README often serves as the basis for more comprehensive user-facing documentation. If you follow this chapter’s example template in your README , your users will likely have what they need to get started. There are additional resources listed in the Resources appendix for writing a detailed and concise README.

### Getting started documentation

Guiding users through first impressions and first-time user experience is the critical role of getting started documentation. Getting started docs are your opportunity to help users get up and running and to build trust with your users that you will guide and support them with good resources. As you write a getting started document, some questions you should ask yourself are:- What are the quickest explanations of what this service is and what its core features do?
- What are the simplest steps to install and use your product?
- What are the most important questions new users will have?
- What are the cool things they can do with your service?

Getting started documentation should translate your user’s interest into them actually developing with your product. If your product is fairly simple, you could show the steps of how to do a basic integration with your product and your user’s code. If your product is more complex, you could provide your users with an inline or downloadable code sample that just needs a few small tweaks to use. It’s better to show your users your product than to tell them about it.

Getting started content also acts as a starting point for more advanced pieces of content. A common mistake organizations make is to only produce advanced documentation, like how-to guides. But you really want to make sure that all types of users are supported, whether they’re advanced or just evaluating your service. You need to help them quickly understand what your product does and what it can do for them. Getting started documentation helps with this problem.

### Conceptual documentation

The next content type is *conceptual documentation* *.* Conceptual documentation helps users understand the concepts and ideas behind your service. It describes how your service works to your users. Conceptual content can be opinionated, but it should avoid implementation details. (Implementation details belong in procedural content, covered later in this chapter.)

Meeting notes, design documents, whiteboard diagrams, and internal documentation are great source material for your service’s conceptual content.

Keep conceptual documentation brief and concise, especially if you’re using conceptual information to set context for a procedure or tutorial. Focus on these sections:

Conceptual guideThe first paragraph, which introduces the concept explained in the document.

**Overview**

Give a technical overview of how the concept works. Describe any additional sub-components or related concepts in sub-sections.

**Related Concept 1**

**. . .**

**Related Concept 2**

**. . .**

**Additional resources**

List any related documentation, including tutorials and how-to guides that implement the concept.

Limit the number of concepts explained in a single document. Readers are generally good at absorbing one core concept at a time. If you’re explaining several new concepts, things get complex very quickly and users may struggle. By keeping conceptual documentation simple for your readers, beginners will feel comfortable learning about your service, and advanced users will appreciate the efficiency it affords them.

NoteConceptual documentation offers a good opportunity for simple user research. Ask a user to read a draft, and then ask them to explain what they read. Evaluate which concepts made sense to them and which ones did not. Improve your document based on this feedback and repeat the exercise as many times as needed.

This user research exercise also shows you other content to include in your documentation plan. Not only does iterative user research improve your conceptual documentation, it helps you identify gaps that you can fill with other types of documentation.

### Procedural documentation

The next type of user content is *procedural documentation*  . Procedural content includes tutorials and how-to guides—anything from installation instructions to API integrations. A procedural document shows readers how to accomplish a specific goal by following a set of structured steps. A single step should describe a single action that a user takes.

People read documentation to solve a problem or accomplish a task, and they want to do so as quickly and effectively as possible. These are some useful patterns for writing guides and tutorials:- Make the guide stand on its own as much as possible with all the actions users need on a single page.
- Keep the number of steps limited to what’s necessary for your users. When a procedure contains many steps, the procedure looks overwhelming and complex to users. Longer procedures also create more opportunities for mistakes and tend to require more maintenance.
- Avoid lengthy explanations. A few sentences of explanation or a well-placed image is useful, but too much additional content within a procedure tends to overwhelm users. A good practice is to write procedures that allow a user to see two or more steps on a standard monitor screen. If you find your procedure contains many explanations, consider separating that information out into a conceptual guide. Note that this doesn’t apply to code examples.

#### Tutorials

A *tutorial* is a procedure that teaches users how to achieve a specific goal. Tutorials  help users test an integration without implementing real code. Good tutorials provide users with an environment they can use for learning and may even offer test data or tools to use.

If your tutorial includes more than ten steps, you’re trying to solve for a use case that’s too complex, or you’re combining too many actions in one document. Long, time-consuming tutorials make it less likely that a user will successfully finish.

If you can’t condense a long tutorial—or any procedural content, for that matter—into fewer steps despite your best efforts, it could mean the service itself is too complex. There may be steps that should be combined, automated, or omitted from the service—and that’s a conversation you should have with the product developers .

NoteComplex documentation helps you identify potential user challenges and can be an opportunity to improve the service itself. Discuss with your development team whether spending multiple hours on a single document is the user experience your organization wants. If, on the other hand, you’re the one who introduced the complexity into the system, that should be a much easier conversation.

#### How-to guides

*How-to guides* are the core type of procedural content. A how-to guide shows how users can solve actual business problems by performing specific steps with your service.

How-to guides  are a true differentiator for your users: a single document that helps them build a solution to their problem. While tutorials focus on learning, a how-to guide is based on action with users implementing real code.

How-To GuideThe first paragraph, which introduces the core concepts and gives overview information required for this guide.

**Prerequisites**

List any steps your users should do before they follow the steps in this guide.

**Steps**

1.

2.

3.

4.

5.

. . .

**Next steps**

Link to additional documentation the user should follow after doing the steps in this guide.

When planning how-to guides, pay attention to your users’ needs and interpret your company’s strategy of what you want your users to do. Plan carefully and be selective, as how-to guides are labor-intensive to write and maintain. You could lead users astray by documenting edge cases at the outer boundaries of your service’s capability .

A good pattern for writing how-to guides is to keep words simple, make actions clear, and continuously reinforce the problem the guide solves.

Include prerequisites at the start of your guides. Prerequisites include any dependencies, such as installing a required version of your system or packages. If specialist skills and knowledge are truly required, list them as a prerequisite, but avoid this whenever possible. Assessments of knowledge or skills are often subjective and add unnecessary requirements. Prerequisites not only tell users what they need to accomplish a goal; they also provide users with an escape hatch.

NoteEscape hatches are helpful cues that signal to a user that they’re probably not in the right place and show them more suitable options. Escape hatches can include links, a callout, or a note with useful context.

Effective how-to guides keep users on a single page as much as possible. It’s tempting to use a link every time another page exists for a term or concept that you mention, but clicking too many links adds more distractions for users. As opposed to Wikipedia, which uses links liberally to teach you new things you didn’t know existed, you can help your users focus by creating a how-to guide on a single page.

Users come  to your documentation with a specific problem in mind, and you want to help them solve that problem as quickly as possible. If they’re jumping from link to link across your documentation site, they’re getting farther away from a solution to the problem they came there to solve. Some overeager users may be tempted to learn everything you’re giving them. They may think, *If they're linking to a concept, it’s probably important*, which could quickly leave them with an overwhelming number of open tabs. Your goal is to provide a guided experience with helpful guardrails to keep users on track.

Links in the middle of your document may distract readers. Instead, provide links to additional resources at the bottom of the page. Linking to related concepts and next steps helps build trust with users by presenting them with the greater context in which a particular guide fits and helps take them to the next step in their user journey .

### Reference documentation

When your users are ready to start building, they lean heavily on your reference documentation. While procedural and conceptual documentation educate and inform, reference documentation  is all about cause and effect: which actions produce which results. This is also true for troubleshooting. Sometimes users encounter errors or friction, and reference documentation helps them quickly get back on track.

#### API reference

API documentation is a trusted reference for your users to start building. Good API documentation:- Provides a detailed reference for all its resources and endpoints
- Offers plenty of examples
- Lists and defines status codes and error messages

An API reference should be concise and minimalistic. It’s a good practice to introduce your API by sharing important information like the standards it follows and how responses are formatted (for example, REST and JSON) and then showing users how to authenticate. You can also use your product documentation to demonstrate lengthier procedures for interacting with your API.

The best way to provide a comprehensive reference of your API is to annotate your code with descriptive comments and autogenerate a reference from the source.[3](#Fn3) This saves you the trouble of manually creating many pages of documentation and offers a more complete reference by tying the content to the code .

Your API reference should define all resources and their endpoints, methods, and parameters, while offering an example request and example response to that request. Chapter [5](505277_1_En_5_Chapter.xhtml) covers best practices for code examples.

Listing and defining status codes and error messages is a great way to conveniently support your developers. In your documentation, explain the error messages developers may encounter when using your API, along with what error codes mean and how to resolve them .

Developers are accustomed to an API reference existing separately from the product and the rest of the documentation. While conceptual and procedural documentation offers more context, an API reference is rooted in a service’s code. An API reference serves as the source of truth for developers to integrate with your service. Once they start building, they’ll depend heavily  on this reference.

NoteThere are many useful resources available to build a reference that best suits the needs of your developers. See the Resources appendix at the end of this book for more information.

#### Glossary

Any complex system has terms with unclear meanings. A *glossary* is a collection of terms and definitions that are specific to your service, field, or industry.

A glossary  helps you use terms consistently in your documentation. It’s frustrating for users to see the same term in your documentation defined in different ways or different terms for the same thing. Not only does inconsistency make it difficult to understand a term in context, it also degrades users’ trust, as it indicates that your organization isn’t even sure of a term’s definition. A glossary doesn’t need  to be comprehensive, but it must define the key terms users need to use your service.

NoteLimit external links in glossaries. It’s tempting to link to external sites, especially if you’re using third-party terms. However, external links put your content at the mercy of third parties, trusting that they’ll keep the resource up to date and in the same location.

#### Troubleshooting documentation

Users often find gaps and limitations in your service faster than you can fix them. As you or your users identify known issues in your product, you can document workarounds in a variety of ways using *troubleshooting* documentation .

A documented workaround shows users a solution that may not be intuitive, but still gets the job done despite known limitations. It’s valuable to be transparent with known issues and bugs to save your users time, as they’re going to discover them anyway. Known limitations typically include edge cases—actions that you may not have expected or recommended users to attempt. Be clear with your users about which edge cases are unsupported.

When organizing troubleshooting information, it’s best to avoid too much explanation on why the problem happens and focus instead on the workaround. Make sure you include a solution  (or *fix*) with the description of the problem.

Troubleshooting**Issue 1**

Description:

Steps to fix:

1.

2.

**Issue 2**

Description:

Steps to fix:

1.

2.

. . .

Organize the issues in a way that makes the most sense to your users. You can organize issues by descending order of frequency—from most likely to least likely—or in chronological order of where users might encounter them in their workflow. The important thing is to give your user a logical flow for finding the right information.

When users reach a troubleshooting page, they’re often trying to fix a problem that’s frustrating to them. Help them solve their problem as quickly as possible.

Another type of troubleshooting reference is to list all of your error  messages and provide more information about causes and solutions. This allows users to copy and paste their error message into search and find more context around the issue that they’re having.

A good pattern for documenting error messages is to group them together on a single page. This makes searching by copy-and-paste more efficient. It’s also good to include specific error messages within the procedure or tutorial where  they may occur.

NoteFAQs are a common way to organize troubleshooting information, but it’s better to avoid the question and answer format and instead list your users’ issues and how to solve them. FAQs often become lengthy lists of uncurated questions without a logical flow. If you do decide to create an FAQ, keep it short and focused.

#### Change documentation

A *changelog* provides a helpful historical record for internal teams like support and engineering. Understanding when changes took place and when customers were impacted can be useful information when troubleshooting. Changelogs  are most common in API documentation, where breaking changes or new versions can negatively impact a developer’s existing integration with your service.

Whenever there’s a significant or breaking change, provide information for what, when, and why this occurred. Not only is it helpful in the moment when you’re letting users know that something changed, but if they’re looking backward and trying to troubleshoot an issue, they can see when a change took place that may have affected them .

List changes in chronological order, including data like:- Previously supported versions, integrations, or deprecated features
- Name changes of parameters or important fields
- An object or resource moved

Release notes are another helpful type of documentation. Release notes provide rich context for the changes listed in a changelog. While a changelog can be automated or consist only of a bulleted list with little context, release notes speak directly to your users. Here's the change that took place. Here's why. Here's how it used to be. Here's how it's going to be. Release notes give users context to understand why a change took place. Example entries for release notes include:- New features
- Bug fixes
- Known bugs or limitations
- Migrations

Release Notes**2020–03–18**

Item one- Summary
- Impact
- Reasoning
- Actions required

Item two

. . .

**2020–03–11**

. . .

## Planning your documentation

Now that you understand the content types and patterns that best serve your users, you can create a documentation plan. A documentation plan functions as a flexible outline, making it easy to map out a user journey through the content you write.

A good documentation plan allows you to:- Anticipate and meet your user’s needs for information
- Get early feedback from users and internal stakeholders on your direction
- Identify gaps and shortcomings not just with your documentation, but the user journey for your service altogether
- Coordinate writing, organizing, and publishing your documentation with other stakeholders

Creating  a documentation plan is often straightforward, but easily overlooked. If you start writing documentation before creating a plan, you might miss critical information your users need or overlook problems they are trying to solve. Without a plan, it’s difficult to think about your user journeys holistically.

To build your documentation plan, answer the following questions which will help you focus on the right information for your users. You already gathered some of this information in your user research (see Chapter 1), but it’s useful to restate it at the top of your documentation plan to help you focus and keep the right information in scope.- Who is your target audience? (You might already have a user persona for them.)
- What are the biggest takeaways you want them to have from your launch?
- In order of importance, what features are you releasing?
- What do users expect from your launch?
- Is there any knowledge users need before they start using your product or features?
- What are the use cases you’re supporting?
- Are there known issues or points of friction users could stumble upon?

Answering these questions creates a context—and with your context in place, you can decide what to build. Start planning your documentation with a *content outline.* Your content outline is a list of titles for pages you need to write and each page’s content type.

Your content outline can be a list with a brief explanation of what’s in each document. A content outline for Corg.ly might look like Table 2-1.Table 2-1Content outline

| Title | Content type | Brief description |
| --- | --- | --- |
| Getting Started with Corg.ly | Getting started | A very simple demo for using Corg.ly with links to other documentation |
| Corg.ly: Dog Translation Explained | Conceptual | A technical explanation of how Corg.ly works |
| Authenticating with Corg.ly’s API | How-to | A step-by-step procedure for authenticating with Corg.ly’s API |
| Translating Dog Barks to English | How-to | A step-by-step procedure for translating dog barks into English |
| Translating English into Dog Barks | How-to | A step-by-step procedure for translating English into dog barks |
| Corg.ly API Reference | API reference | List of all API calls and their syntax |
| Troubleshooting Audio Issues | Troubleshooting | Common issues with translating audio and managing audio files |
| Release Notes | Changelog | Release notes for this Corg.ly release |

If your documentation plan reflects a coherent journey for your users, you’re probably in good shape. If your plan feels like a maze or it’s unclear what a user needs to do to accomplish a task or solve their problem, then go back and reshape the documentation plan. You may need to interview more users or internal stakeholders. If the problem isn’t with the documentation plan, then it may point to an overly complex service that needs improvement before a clear user journey can emerge.

Get feedback from others on your documentation plan before you begin writing. For more information on reviews, see Chapter [4](505277_1_En_4_Chapter.xhtml).

Once you have your documentation plan, you can start writing and editing content (described in Chapters [3](505277_1_En_3_Chapter.xhtml) and [4](505277_1_En_4_Chapter.xhtml)). You can also list additional items your documentation needs to improve the overall user experience. These include integrating code samples (described in Chapter [5](505277_1_En_5_Chapter.xhtml)) and visual content like diagrams and videos (Chapter [6](505277_1_En_6_Chapter.xhtml)). You can also start the rough outline of a publishing plan (Chapter [7](505277_1_En_7_Chapter.xhtml)), considering where your documentation will be published and your timeline for publishing.

## Summary

This chapter guides you through how to turn the empathy you gained in Chapter [1](505277_1_En_1_Chapter.xhtml) into action with a documentation plan, which outlines the content and content types you need to create before you start writing. Content types are different ways to present information. Different content types help solve different kinds of problems. Content types include code comments, READMEs, getting started, conceptual, procedural, and reference documentation. Each of these types follows different patterns, and building content based around these patterns helps create effective and consistent documentation.

A documentation plan functions as a flexible outline of the content that your users need and ensures that you’re focusing on writing the most important documentation. The next chapter shows you how to turn your documentation plan into actual documentation.

Footnotes1B.J. Keeton, “How to comment your code like a pro,” Elegant Themes, published April 3, 2019, [www.elegantthemes.com/blog/wordpress/how-to-comment-your-code-like-a-pro-best-practices-and-good-habits](http://www.elegantthemes.com/blog/wordpress/how-to-comment-your-code-like-a-pro-best-practices-and-good-habits).

2Omar Abdelhafith, “README.md: History and components,” Medium, published August 13, 2015, [https://medium.com/@NSomar/readme-md-history-and-components-a365aff07f10](https://medium.com/%2540NSomar/readme-md-history-and-components-a365aff07f10).

3Shariq Nazr, “Say goodbye to manual documentation with these 6 tools,” Medium, published March 30, 2018, [https://medium.com/@shariq.nazr/say-goodbye-to-manual-documentation-with-these-6-tools-9e3e2b8e62fa](https://medium.com/%2540shariq.nazr/say-goodbye-to-manual-documentation-with-these-6-tools-9e3e2b8e62fa).
