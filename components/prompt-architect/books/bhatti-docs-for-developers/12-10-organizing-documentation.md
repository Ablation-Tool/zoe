© The Author(s), under exclusive license to APress Media, LLC, part of Springer Nature 2021J. Bhatti et al.Docs for Developershttps://doi.org/10.1007/978-1-4842-7217-6_10
# 10. Organizing documentation

Jared Bhatti1, Zachary Sarah Corleissen2, Jen Lambourne3, David Nunez4 and Heidi Waterhouse5(1)Berkeley, CA, USA(2)Victoria, BC, Canada(3)Cornwall, UK(4)San Francisco, CA, USA(5)Mounds View, MN, USA
## Corg.ly: The next release

*“Charlotte, I have a few ideas for our next release,” Karthik said. “I shared a design doc with you when you have a minute.”*

*Charlotte took a few minutes to read through the document. “This looks great!” she said. “I like how you’ve thought about adding video support. I think that will give us better results in our translations.”*

*“Thanks!” replied Karthik. “This was the most frequent request from customer feedback. I even wrote up a few docs for customers who want to try video support as an alpha feature.”*

*After an alpha release and publication, Charlotte and Karthik reached out to Mei for her feedback and set up a meeting.*

*“Thanks for reaching out,” Mei responded. “My team was excited by the announcement, but we had trouble finding the right information on how to send the Corg.ly service a video and get back the translation text.”*

*Karthik thought for a second. “I definitely documented that. Here, let me show you.” After clicking through the Corg.ly documentation site several times, he spun his laptop around. “I know it’s buried deep in the site, but we did document it.”*

*Mei frowned. “Oh, I see. Without the link you sent me directly, I don’t think I would have found that on my own.”*

![../images/505277_1_En_10_Chapter/505277_1_En_10_Figa_HTML.png](/api/v2/epubs/urn:orm:book:9781484272176/files/images/505277_1_En_10_Chapter/505277_1_En_10_Figa_HTML.png)

*Karthik and Charlotte exchanged glances across the room. They hadn’t thought about how to organize their content for their readers. If Mei was having this issue, their other customers definitely were too. Back to the whiteboard to come up with a plan...*

## Organizing documentation for your readers

In previous chapters, you defined your audience, drafted your content according to common documentation types, and published your content. As you publish more and more pages, you might find yourself with a growing set of unorganized content that readers find difficult to navigate and understand. It’s time to start thinking about how you organize your documentation.

Defining how you organize your content helps you grow your documentation in a structured and sustainable way. How you organize content conveys meaning and purpose to your readers. The organizational structure you apply to your documentation is called its *information architecture* .

A clearly defined information architecture helps you and your fellow developers add pages to your site and scale up the number of documents you publish without confusing your readers or making your site difficult to navigate.

To help you build an information architecture for your documentation, this chapter guides you through:- How to help your readers find the right content
- Designing your information architecture
- Implementing your information architecture

## Helping your readers find their way

Imagine you’re entering an unfamiliar airport and trying to find the right gate for your plane. As you scan your surroundings, you’re on the hunt for clues as to where you are. You might first look to see if there is a map or signs indicating which terminal you’re in. Then, you might search for indicators telling you which floor you’re on and where you can go to check your luggage.

When your users search through your set of documentation for a specific piece of information, they’re similarly scanning their surroundings for clues as to whether or not they’re in the right place and where to go next. This scanning process is very fast, and it’s focused on identifying patterns in your content to find relevant information. Depending on the complexity of your product, your readers might encounter dozens or even hundreds of pages containing distinct bits of information with varying degrees of relevance.[1](#Fn1)

You can help your users navigate your site faster and more intuitively by organizing information into a meaningful structure, intentionally surfacing your pattern of organizing content, and highlighting information that is most relevant to your users. Doing this helps your readers build a map in their mind, or a *mental model* , of how your content is organized.

Planning your information architecture, and helping your readers build a mental model of your content means incorporating new elements into your set of documentation, including:- Site navigation and organization
- Landing pages
- Navigation cues

NoteThis section merely scratches the surface of information architecture, focusing on how it relates to documentation. For more resources on information architecture and how it relates to user experience, see the Resources appendix.

### Site navigation and organization

Your site navigation is both a map for your existing content and your blueprint for where to publish additional content. It’s the most important part of your information architecture, so it’s important to build it thoughtfully.

There are three basic ways to organize your content: sequences, hierarchies, and webs.[2](#Fn2) These architectures govern the possible ways for you to create a consistent model for users to navigate your site, and for you to add additional pages.

#### Sequences

Sequentialstructures are the most familiar to any reader (Figure 10-1). Any book you read is organized in sequential order—one page after another. Sequential ordering may be chronological, like the steps required to use an API, or may be alphabetical, like an index or glossary. Sequential order requires you, the writer, to put the pages in the most effective order for your reader.![../images/505277_1_En_10_Chapter/505277_1_En_10_Fig1_HTML.jpg](/api/v2/epubs/urn:orm:book:9781484272176/files/images/505277_1_En_10_Chapter/505277_1_En_10_Fig1_HTML.jpg)

*Figure 10-1Sequential structure*

#### Hierarchies

Hierarchicalstructure is similar to a family tree or an organizational chart (Figure 10-2). Like a family tree, content has a parent/child relationship between pages. In a hierarchical structure, you start from one broad idea and narrow down into more detailed and increasingly specific information. One main topic is supported by multiple related subtopics beneath it.![../images/505277_1_En_10_Chapter/505277_1_En_10_Fig2_HTML.jpg](/api/v2/epubs/urn:orm:book:9781484272176/files/images/505277_1_En_10_Chapter/505277_1_En_10_Fig2_HTML.jpg)

*Figure 10-2Hierarchical structure*

#### Webs

Webs are interconnected, non-hierarchical patterns of pages where each page links to one or more pages (Figure 10-3). This allows your user to decide how to view and organize your content. Wikipedia, for example, has a web organization. Each page is at the same level in the hierarchy, and is linked to one or more pages in the set, allowing you to seamlessly read from one topic to the next, traversing any linked order you choose.![../images/505277_1_En_10_Chapter/505277_1_En_10_Fig3_HTML.jpg](/api/v2/epubs/urn:orm:book:9781484272176/files/images/505277_1_En_10_Chapter/505277_1_En_10_Fig3_HTML.jpg)

*Figure 10-3Web structure*

#### Bringing it all together

Your site navigation and organization likely uses a combination of sequences, hierarchies, and webs. For example, the landing page for Corg.ly’s documentation might be hierarchical based on different user needs, but each section contains sequential how-to pages to Procedural guides step by step through the process of accomplishing a task (Figure 10-4).![../images/505277_1_En_10_Chapter/505277_1_En_10_Fig4_HTML.png](/api/v2/epubs/urn:orm:book:9781484272176/files/images/505277_1_En_10_Chapter/505277_1_En_10_Fig4_HTML.png)

*Figure 10-4Sample architecture*

Although there are many different ways to categorize information, your information architecture should always feel consistent and familiar for a reader to navigate. For example, if Corg.ly had two services, one that translates dog barks through an app on phones carried by humans, and one for translation collars worn by dogs, it might make sense to have a document structure and navigation that looks like Figure 10-5.![../images/505277_1_En_10_Chapter/505277_1_En_10_Fig5_HTML.png](/api/v2/epubs/urn:orm:book:9781484272176/files/images/505277_1_En_10_Chapter/505277_1_En_10_Fig5_HTML.png)

*Figure 10-5Sample architecture*

The users of each product may be different, but there’s enough crossover between them that it’s helpful to keep your information architecture consistent. A consistent information architecture also helps you know where to add new content. If a developer writes a new set of procedures for using a new feature of a translation collar, it’s clear in the information architecture where that content goes.

### Landing pages

*Landing pages*  are pages that route users to the right content with minimal reading required, building trust with users by saving them time. A landing page should be short, easy to scan, devoid of jargon, and surface useful information for your reader. Landing pages are equivalent to a huge signpost in the road that points to the possible directions your users can go.

To make a good landing page, you must prioritize your users’ needs first. Your landing page should highlight the most important and relevant information for your users. Create guardrails to guide your users down the right path, and hide complexity that most users don’t need right away. Your user research (from Chapter [1](505277_1_En_1_Chapter.xhtml)) and your company’s strategic goals can help define the top-level categories on your landing page.

For example, the main landing page for Corg.ly documentation might have three major sections on the main page, each targeted at the most common user tasks (Figure 10-6):- A Getting Started section that includes an overview of the Corg.ly service and a quick tutorial.
- Two of the most used how-to guides for what users want to accomplish with Corg.ly: “Translating barks to English”, and “Translating English to barks”.

![../images/505277_1_En_10_Chapter/505277_1_En_10_Fig6_HTML.png](/api/v2/epubs/urn:orm:book:9781484272176/files/images/505277_1_En_10_Chapter/505277_1_En_10_Fig6_HTML.png)

*Figure 10-6Example landing page*

A landing page lets a user choose their topic, and prepares them to find a resource that helps them accomplish a task or learn more about how to accomplish the task. Make sure the links on landing pages take users directly to documents—the fewer clicks required for users to get to a document from the landing page, the better.

As the service grows, the number of items on the landing page can increase. For example, if a number of advanced users need quick access to the API reference pages, it’s useful to add that to the main landing page. However, it’s important to limit the number of links on the page to the most important items for users.

You can add additional landing pages as features grow. For example, if Corg.ly launches support for a number of different mobile applications and a number of devices like translation collars, it might be useful to create a landing page for each different service.

Avoid creating unnecessary landing pages or nesting too many landing pages under one another. Nesting landing pages under yet more landing pages requires too much sifting from users to find the document they’re looking for, and makes it more confusing when you add additional pages.

### Navigation cues

Most users will arrive at your documentation through search, by putting terms in a search engine and clicking on the first, most relevant result. This might get them to the right piece of information, but more likely than not, it will simply get them close.

Unfortunately, close isn’t helpful if users don’t know how close they are, or how to navigate from a page that’s close to the actual page they’re looking for. This is where *navigation cues* can help.

Navigation cues surface your information architecture to your readers, helping them understand where they are in relation to the rest of your content, and where to go next. It's the red dot on a map that says “You are here”.

Navigation cues include elements like:- **Breadcrumbs** that show where a particular page sits in a content hierarchy by displaying its parent pages
- **Side navigation** that shows the content hierarchy for the entire site, or a large portion of the site
- **Labels and metadata** that contain information relevant to the document, typically machine readable for help with search indexing
- **Prerequisites, next steps, and additional information sections** that are succinct and informative, directing users where to go next, or what they should have read before arriving at a page
- **Escape hatches**, often in the form of callouts, that offer recommendations for alternative pages if a reader ends up on the wrong page

While navigation cues are crucial, use them economically. If you’ve ever found yourself at an intersection staring at a guidepost with signs pointing in every possible direction, you know that too many pointers create confusion instead of clarity. Users get decision fatigue and become overwhelmed at the number of options when negative space (space with nothing in it) would serve them better.

## Organizing your documentation

Organizing your documentation means assessing your existing content, planning and building an information architecture, and migrating content into this new organizational scheme. The goal is to create the best organizational structure for your content that helps your users find what they need *and* that you can maintain and scale over time.

The following sections guide you through the process of assessing a collection of content, determining how it should be organized, and implementing a new information architecture. It assumes that you know what your users’ needs are, and how they’re navigating and reading your content, based on user research, user feedback, and documentation metrics.

### Assess your existing content

The first step to organizing your documentation and building an information architecture is to create an assessment of your existing content. The goal is to create a list of all the content you currently have and understand how well its location is serving your users.

Think of assessment as a flow chart that starts at the top of your site and goes through each page in your documentation. To start, list each page of documentation in your site in a spreadsheet, including the page title and URL. Next, evaluate each page in the list, using what you know about your users to determine how well each page is working. Ask yourself the following questions:- Is this page useful?
- Is this page up to date?
- Is this page in the right place?

As you evaluate each page, label it with what work needs to be done. Example labels include:- Keep
- Remove
- Review for accuracy
- Merge with another document
- Split into multiple documents

After assessing your existing content, ask yourself, is there missing information that your users have been requesting? This missing content is called a *content gap* . Make a list of all the content gaps you find and add them to your assessment.

From this exercise, you now have a list of all the content that *should* be in your new information architecture. You also have a list of new content to create, edit, or remove to improve your set of documentation.

### Outline your new information architecture

After assessing your existing content, consider what an ideal map of your content would look like. This is your chance to map out how your content should be organized to best support your users.

As you create this new map, consider the *mental model*  that your users have for your documentation. How do your users expect your documentation to be organized? How can you best guide them to the right information?

Ultimately, users expect your content to be:- **Consistent:** Your content is organized with familiar structure and patterns. Users always know where they are.
- **Relevant:** The most important content that addresses the most common user needs is the easiest to find.
- **Findable:** Your content is easily accessed from any homepage or landing pages, and through search.

With these principles in mind, make sure your map includes consistent patterns for your content. For example, if you have a list of procedures documented, you probably want to list them in chronological order. If you have a list of conceptual information, you might want to organize it based on what’s most important to your users first.

As you try different organizational schemes and get feedback from users, you might have to work through several iterations of your information architecture. *Card sorting*  can be a good way to experiment with different structures.[3](#Fn3)

Card sorting is exactly what it sounds like: you create an index card for each page in your site, including landing pages. Then, you move the cards around until you create your desired site organization. Putting page names on cards makes them easy to move, letting you play with different orders and organizational schemes for your information and quickly get feedback from your users.

Aim for an information architecture that’s neither too deep nor too shallow. If one section of the site is too deep, consider ways of dividing that content into different groups. Likewise, if you have a section with only one page in it, consider whether to merge the page into another.[4](#Fn4)

As you settle on an outline for your content, verify your new information architecture serves the needs of your users. Consider the common tasks that your users perform with your documentation, and ask yourself:- Does each common task have a clear starting point?
- Is the next step for each task clearly defined?
- Are there any missing steps (content gaps) that need to be added?

If the answer to any of these questions is no, consider adding additional landing pages, navigation cues, or additional content to address the issue.

NoteWhat if a document fits in multiple locations? Automated content reuse is a tempting option as your documentation set grows, but use it sparingly. Do it when it’s best for your users, not for your organization. Automated reuse can hurt search results and confuse your readers, and the technical complexity of automation can make maintenance difficult.

You’re better off settling the document in a single best location and linking to it from multiple places as necessary.

### Migrate to your new information architecture

Once you’re happy with your information architecture and you’ve gotten enough user feedback and validation, it’s time to migrate to your new organizational structure. As you move the pages around, use this validation checklist as an auditing mechanism:- **Landing pages**: created sparingly and guiding users to the most important documents
- **Content types**: consistently implemented and suitable for your users
- **Page data**: descriptive and consistent titles, headers, prerequisites, and next steps
- **Navigation cues**: breadcrumbs, side navigation, and escape hatches to help orient users
- **Labels and metadata**: display relevant data for users and search index
- **Redirects:** users are redirected from previous locations to new URLs after you move pages

It’s also important to document your information architecture: note the decisions you made, the user research and feedback it was based on, and the patterns used for the information architecture. This document doesn’t need to be a significant undertaking. Even a compact resource with a site map and collection of templates creates consistency for your users and alignment within your organization.

### Maintaining your information architecture

When you add new pages to your documentation, consider the following questions:- Is it clear where this new content belongs?
- What adjustments to the existing information architecture are required?
- Does this content impact the home page and landing pages?

A well-thought out information architecture allows you to answer these questions quickly and easily, helping you scale your content while confidently knowing where your content will be published. However, as your product and documentation evolve, keep verifying your users’ mental models for your site. When a big release or update results in many pages changing, you should evaluate your information architecture and make the required changes to support your users.

## Summary

Information architecture is the organizational structure you apply to your documentation. Information architecture helps your readers assemble a map in their minds of how to navigate your content. To communicate your information architecture to your readers, you should integrate site navigation, landing pages, and navigation cues into your set of documentation.

There are three basic ways to organize your content: sequences, hierarchies, and webs. These architectures govern the possible ways for you to create a consistent model for users to navigate your site, and for you to add additional pages.

When designing your information architecture, build an inventory of your existing content, assess your inventory for any content gaps, and organize your set of content into a new information architecture.

The next chapter covers how to maintain documentation over time, including deprecating content when it’s no longer relevant.

Footnotes1“First Impressions Matter: How Designers Can Support Humans’ Automatic Cognitive Processing”, Therese Fessenden, Nielsen Norman Group, accessed 27 June 2021, [https://www.nngroup.com/articles/first-impressions-human-automaticity/](https://www.nngroup.com/articles/first-impressions-human-automaticity/).

2Patrick Lynch and Sarah Horton, *Web Style Guide*, Yale University Press; fourth edition (2016)

3“Card Sorting”, usability.gov, accessed June 20, 2021, [https://www.usability.gov/how-to-and-tools/methods/card-sorting.html](https://www.usability.gov/how-to-and-tools/methods/card-sorting.html).

4Heidi McInerney, “How to Build Information Architecture (IA) that’s a ‘No Brainer’”, Vont, accessedJune 20, 2021, [https://www.vontweb.com/blog/how-to-build-information-architecture/](https://www.vontweb.com/blog/how-to-build-information-architecture/).
