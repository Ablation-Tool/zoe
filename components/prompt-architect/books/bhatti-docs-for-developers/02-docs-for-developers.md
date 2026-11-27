Jared Bhatti, Zachary Sarah Corleissen, Jen Lambourne, David Nunez and Heidi Waterhouse
# Docs for Developers

## An Engineer’s Field Guide to Technical Writing

1st ed.Foreword by Kelsey Hightower![../images/505277_1_En_BookFrontmatter_Figa_HTML.png](/api/v2/epubs/urn:orm:book:9781484272176/files/images/505277_1_En_BookFrontmatter_Figa_HTML.png)

Logo of the publisherJared BhattiBerkeley, CA, USAZachary Sarah CorleissenVictoria, BC, CanadaJen LambourneCornwall, UKDavid NunezSan Francisco, CA, USAHeidi WaterhouseMounds View, MN, USA ISBN 978-1-4842-7216-9e-ISBN 978-1-4842-7217-6https://doi.org/10.1007/978-1-4842-7217-6© Jared Bhatti, Zachary Sarah Corleissen, Jen Lambourne, David Nunez, Heidi Waterhouse 2021This work is subject to copyright. All rights are reserved by the Publisher, whether the whole or part of the material is concerned, specifically the rights of translation, reprinting, reuse of illustrations, recitation, broadcasting, reproduction on microfilms or in any other physical way, and transmission or information storage and retrieval, electronic adaptation, computer software, or by similar or dissimilar methodology now known or hereafter developed.Trademarked names, logos, and images may appear in this book. Rather than use a trademark symbol with every occurrence of a trademarked name, logo, or image we use the names, logos, and images only in an editorial fashion and to the benefit of the trademark owner, with no intention of infringement of the trademark. The use in this publication of trade names, trademarks, service marks, and similar terms, even if they are not identified as such, is not to be taken as an expression of opinion as to whether or not they are subject to proprietary rights.While the advice and information in this book are believed to be true and accurate at the date of publication, neither the authors nor the editors nor the publisher can accept any legal responsibility for any errors or omissions that may be made. The publisher makes no warranty, express or implied, with respect to the material contained herein.This Apress imprint is published by the registered company APress Media, LLC part of Springer Nature.

The registered company address is: 1 New York Plaza, New York, NY 10004, U.S.A.

ForewordIf a new software project is created and there are no docs around to learn it, does it work?

Most of your potential users will never know because they’ll never find your project, and if they do, they’ll have no clue how they’re supposed to use it. This is an all too common problem, and as a software developer myself, I can honestly say I spend too much of my time reverse engineering command line tools, libraries, and APIs that lack adequate documentation necessary to complete the task at hand.

If developers are the superheroes of the software industry, then the lack of documentation is our kryptonite.

I’ve often joked that “Good developers copy; great developers paste.” To understand why, you have to dig into the workflow used by most software engineers when faced with a problem. Our usual workflow looks like this:1. 1.Attempt to understand the problem.
2. 2.Search for an existing solution everywhere we can think to look.
3. 3.If we’re lucky enough to find one, we prove to ourselves the solution works.
4. 4.We push the solution we found to production.

This is what we call the “developer loop,” and the most successful projects have documentation to guide developers through each of these steps. It’s because documentation is a feature. In fact, it’s the first feature of your project most users interact with, because it’s the first thing we look for when trying to solve a problem.

So it begs the question, why is documentation often deprioritized or missing altogether?

It’s not because we’re not invested in it, nor is it because we aren’t good writers. It’s because many of us don’t know how to do it. It’s because we, as developers, rarely understand that in addition to the developer loop, there’s an equally important “writer loop.”

The writer loop is similar to how we write code. It requires you to understand the problem your users are trying to solve, create a plan for solving it, use common design patterns, and write the content that solves the issue. The developer loop and the writer loop are two sides of the same coin. During the writing loop, we’re creating information our users want during the developer loop. Knowing how to bring these two loops into alignment helps both your project and your users succeed.

I realized this myself when introducing new developers to Kubernetes. Developers wanted to know how all the pieces of Kubernetes fit together, but there wasn’t any content that helped them. I found out quickly that you have about five minutes to help developers find the information they need before they abandon your project and move on to something else.

That’s what led me to write *Kubernetes the Hard Way*, a hands-on approach that now has over 27,000 stars on GitHub. Likewise, when developers were seeking information on how to quickly get Kubernetes up and running for their infrastructure, I worked with co-authors to write the aptly named book *Kubernetes: Up and Running*.

Through these experiences, I learned more than I ever wanted to know about the writer loop and how necessary it is to developers. That’s why I was excited to learn about this book.

The authors of this book have worked on documenting several difficult technical projects at places like the Linux Foundation, Google, Stripe, LaunchDarkly, and the UK government, working to meet developers’ needs through documentation. In this book, they distill their experience into a step-by-step process that you can apply to any project, along with case studies, tutorials, and tips based on hard-won experience.

So, here it is: The book you’re holding guides you through the phases of the writer loop by leveraging real-world situations and a workflow that is so pragmatic and effective that I’ve been using parts of it over the years and didn’t even know it.

I’ve gone on and on about the importance of the processes presented in this book, but you probably only care that it works. It does.> —Kelsey Hightower

Praise forDocs for Developers> *“Add documentation” is a step in every product release plan, and “we need more docs” is an action item from every internal developer productivity survey, but it’s surprisingly difficult to translate those concise goals into useful documentation. Docs for Developers reveals the repeatable process behind incredible documentation.*
> 
> —Will Larson, CTO at Calm, author of *An Elegant Puzzle* and *Staff Engineer*

> *Great documentation is an often overlooked yet critical component for ensuring the success and large scale adoption of a software project. Docs for Developers is a must-read for developers and technical writers who want to rapidly accelerate their ability to create documentation that is easy to consume, brings joy to end users, and is capable of dramatically improving business results.*
> 
> —Brad Topol, IBM Distinguished Engineer, Open Technology and Developer Advocacy. Co-author of *Kubernetes in the Enterprise*, and *Hybrid Cloud Apps with OpenShift and Kubernetes*

> *No matter your starting point, you can find techniques and advice to improve your documentation in Docs for* Developers. *This book does for dev docs what The Phoenix Project does for devops - makes your aspirations attainable. The API startup story kept me reading and the cute corgi pictures made me smile.*
> 
> —Anne Gentle, Developer Experience Manager at Cisco. Author of the book *Docs Like Code* and website [docslikecode.com](https://docslikecode.com).

> *Good documentation is a multiplier that helps people onboard and explore software. Docs for Developers guides developers and technical writers to document what their users care about, organize content to help users find what they need, and measure how documentation helps users understand and adopt their software**.*
> 
> —Stephanie Blotner, Technical Writing Manager at Uber

> *Docs for Devs condenses years of knowledge from multiple industry leaders into a concise, actionable framework. This book guides you from planning to production, with hard won insights on every page. Read it today; your users will thank you.*
> 
> —Eric Holscher, Co-founder of Write the Docs and Read the Docs

IntroductionIt’s four AM and your pager goes off. Your company’s service has crashed and clients are panicking. You scramble through a half-familiar code base, searching for the root cause. The error messages in the unit tests are frustratingly unspecific, and the internal README consists of headings followed by repeating one-word paragraphs: [TODO].

*Who wrote this*, you wonder. With a sinking feeling, you realize you’re looking at your own code from fourteen months ago, and you’ve forgotten almost everything about it.

You search your memory for any reminder of what you were doing, why you did it this way, and whether you’d peer-reviewed or tested for a particular set of edge cases. Meanwhile, your clients open support ticket after support ticket, demanding answers.

Your own words come back to haunt you: *the code is self-documenting*.

Or maybe your service is performing great and getting better. As more clients sign on, they have questions. So many questions. Emails and support tickets flood in as your service scales, and you’re increasingly pulled away from development and into support.

As the person most knowledgeable about what you’ve built, you’re doomed to a calendar full of one-on-one support meetings, answering the same question from six different people. You know you could fix the problem if you had an opportunity to research and write down how things work, but you’re so busy replying to users’ questions that you never have the time.

Now picture another scenario: your code is commented and your READMEs are accurate and up to date. You have a getting started guide and a set of tutorials that target your users’ top use cases. When a user asks you for help, you point them to documentation that’s genuinely helpful. That four AM pager alert? It took five minutes to resolve because you found what you needed with your first search.

Effective developer documentation makes the last scenario possible.

You might have heard the often-misquoted saying that *good code documents itself*. It’s true that good naming, types, design, and patterns make code easier to understand. But projects with sufficient complexity and scale (that is, most projects worth building) need human-readable documentation to help others quickly understand what you’re building and how to use it.

The authors of this book have helped a number of organizations create great developer documentation, including large tech companies, fast moving startups, government agencies, and open source consortiums. We each have years of experience creating developer documentation, listening to and working with developers, and generally being immersed in every aspect of developer docs at every scale.

We’ve helped innumerable developers out of the nightmare scenarios described above. The more we helped, the more we realized that there wasn’t a primer for developers looking to create documentation. So, we went to work, documenting a fix to the problem we observed developers experiencing.

We created this field guide to technical documentation by building on our own expertise and feedback from a multitude of developers. It’s designed as a resource to keep at hand, so you can write documentation as part of your software development process.

This book walks you through creating documentation from scratch. It begins with identifying the needs of your users and creating a plan with common patterns of documentation, then moves through the process of drafting, editing, and publishing your content. The book concludes with practical advice about integrating feedback, measuring effectiveness, and maintaining your documentation as it grows. Each chapter builds sequentially on previous chapters, and we recommend following the book in order, at least on your first read through.

Throughout this book, we weave through stories about a developer team working on a fictional service called Corg.ly. Corg.ly is a service that translates dog barks into human language. Corg.ly uses an API to send and receive translations, and uses a machine learning model to regularly improve its translations.

The Corg.ly team consists of:- **Charlotte:** The lead engineer at Corg.ly, tasked with launching Corg.ly publicly in a month with developer documentation.
- **Karthik:** A software engineer at Corg.ly working with Charlotte.
- **Mei:** One of the first customers for Corg.ly’s translation service.
- **Ein:** Office mascot and beta tester for Corg.ly. A corgi.

Finally, this book is intentionally agnostic about tools and frameworks. It may seem frustrating that we don’t tell you to write in a particular markup language or publish with a particular static site generator that automatically updates with a particular continuous integration tool. Our opacity is intentional: the languages and tools that work best are the ones closest to your own code and tooling.

If, by the end of this book you’re still looking for more guidance on tooling, we provide an appendix of resources you can use to find additional information and the right documentation tools for your needs.

Acknowledgments*A special thanks to everyone who made this book possible, including family and friends that supported us, colleagues that gave us encouragement, and test readers and editors who improved our work enormously. We’d specifically like to thank Riona Macnamara, Brian MacDonald, Sid Orlando, Brad Topol, Kelsey Hightower, Larry Ullman, Stephanie Blotner, Jim Angel, Betsy Beyer, Eleni Fragkiadaki, Lisa Carey, and Eric Holscher for their feedback, input, and encouragement.*

*Individually, we would like to acknowledge the following people.*

*Jared: Immense gratitude to Tegan Broderick who never wavered in her support, and a special thank you to Meggin Kearney and Ryan Powell for giving me the time and space to work on this.*

*Zach: Many thanks to Chris Aniszczyk at the Linux Foundation for supporting documentation in open source. Much love to my mom, Christine Durham, who always knew I had it in me.*

*Jen: Colossal thanks to Luke Wilkinson for being on hand with a squish, a wine, and words of encouragement whenever I questioned if writing a book in a pandemic was a good idea. I will always be your number one subscriber. My immense gratitude to my mum, dad, and little brother Chris for always encouraging me to “write a bloody book”. Chris, you’re one step closer to getting your boat. To my colleagues past and present who teach me something new every day, and especially Eleni Fragkiakadi for her code and diagrams in this book. Thank you to Vince Davis for never losing faith in me, and finally to Rosalie Marshall for being the reason I started writing docs and the reason I’ll never stop.*

*David: My deepest gratitude goes to Katie Nunez for always believing in me, and to Charlotte and Cameron for motivating me to pursue my passion for writing. My love and appreciation go to Lydia Nunez for showing me that the library is the coolest place to be, and to Alfred Nunez for always sharing his newspaper with me. Thank you, Jessica and Stephen for being my best friends and inspiration. Eternal thanks to my current and former technical writing teams who’ve taught me so much. Finally, I’m forever indebted to John Souchak for giving me a chance.*

*Heidi: Enormous thanks to my wife, Megan, for putting up with me muttering about this for a whole pandemic, and to my kids Sebastian and Carolyn, who are good sports about Weird Mom Hobbies. To Laura, who is always my first audience. I’d like to thank my former managers, Adam Zimman and Jess, and my current manager, Dawn Parzych, for giving me the encouragement, space, and time to work on such a big project and for believing in me.*

Table of ContentsChapter 1:​ Understanding your audience1Corg.​ly:​ One month to launch1The curse of knowledge3Creating an initial sketch of your users4Defining your users’ goals4Understanding who your users are6Outline your users’ needs7Validate your user understanding8Using existing data sources9Collecting new data10Condensing user research findings14User personas15User stories16User journey maps17Creating a friction log19Summary21Chapter 2:​ Planning your documentation23Corg.​ly:​ Creating a plan23Plans and patterns24Content types25Code comments25READMEs27Getting started documentation29Conceptual documentation30Procedural documentation31Reference documentation35Planning your documentation41Summary44Chapter 3:​ Drafting documentation45Corg.​ly:​ First drafts45Confronting the blank page (or screen)45Setting yourself up for writing success46Choosing your writing tools47Breaking through the blank page47Defining your document’s title and goal48Creating your outline49Meeting your reader’s expectations50Completing your outline51Creating your draft52Headers53Paragraphs54Procedures54Lists55Callouts56Writing for skimming57State your most important information first58Break up large blocks of text59Break up long documents59Strive for simplicity and clarity60Getting unstuck60Let go of perfectionism61Ask for help61Highlight missing content62Write out of sequence62Change your medium63Working from templates63Finishing your first draft65Summary66Chapter 4:​ Editing documentation67Corg.​ly:​ Editing content67Editing to meet your user’s needs68Different approaches to editing69Editing for technical accuracy70Editing for completeness71Editing for structure72Editing for clarity and brevity73Creating an editing process75Reviewing your document first75Requesting a peer review76Requesting a technical review77Receiving and integrating feedback78Giving good feedback79Summary81Chapter 5:​ Integrating code samples83Corg.​ly:​ Showing how it works83Using code samples84Types of code samples85Principles of good code samples86Explained87Concise90Clear92Usable (and extensible)93Trustworthy94Designing code samples95Choosing a language95Highlighting a range of complexity95Presenting your code96Tooling for code samples96Testing code samples97Sandboxing code98Autogenerating samples98Summary99Chapter 6:​ Adding visual content101Corg.​ly:​ Worth a thousand words101When words aren’t enough102Why visual content is hard to create103Comprehension104Accessibility105Performance106Using screenshots106Common types of diagrams108Boxes and arrows108Flowcharts110Swimlanes111Drawing diagrams112Start on paper116Find a starting point for your reader116Use labels116Use colors consistently117Place the diagram117Publishing a diagram117Get help with diagrams117Creating video content118Reviewing visual content119Maintaining visual content120Summary120Chapter 7:​ Publishing documentation121Corg.​ly:​ Ship it!121Putting your content out there122Building a content release process123Creating a publishing timeline124Coordinate with code releases126Finalize and approve publication126Decide how to deliver content128Announce your docs129Planning for the future129Summary130Chapter 8:​ Gathering and integrating feedback133Corg.​ly:​ Initial feedback133Listening to your users134Creating feedback channels135Accept feedback directly through documentation pages136Monitor support issues137Collect document sentiment138Create user surveys139Create a user council140Converting feedback into action141Triaging feedback141Following up with users145Summary145Chapter 9:​ Measuring documentation quality147Corg.​ly:​ Tuesday after the launch147Is my documentation any good?​148Understanding documentation quality148Functional quality149Structural quality155How functional and structural quality relate158Creating a strategy for analytics158Organizational goals and metrics159User goals and metrics160Documentation goals and metrics162Tips for using document metrics164Make a plan164Establish a baseline165Consider context165Use clusters of metrics166Mix qualitative and quantitative feedback166Summary166Chapter 10:​ Organizing documentation169Corg.​ly:​ The next release169Organizing documentation for your readers170Helping your readers find their way171Site navigation and organization172Landing pages176Navigation cues178Organizing your documentation179Assess your existing content179Outline your new information architecture181Migrate to your new information architecture183Maintaining your information architecture184Summary184Chapter 11:​ Maintaining and deprecating documentation187Corg.​ly:​ A few releases later187Maintaining up-to-date documentation188Planning for maintainability189Align documentation with release processes190Assign document owners192Reward document maintenance193Automating documentation maintenance193Content freshness checks194Link checkers195Linters195Reference doc generators196Removing content from your docset196Deprecating documentation197Deleting documentation198Summary199Appendix A:​ When to hire an expert201Meeting a new set of user needs202Increasing support deflections202Managing large documentation releases202Refactoring an information architecture202Internationaliza​tion and localization203Versioning documentation with software203Accepting user contributions to documentation203Open-sourcing documentation204Appendix B:​ Resources205Courses205Templates206Style guides207Automation tools207Visual content tools and frameworks209Blogs and research210Books211Communities212Bibliography215Index221About the AuthorsJared BhattiJared (he/him) is a Staff Technical Writer at Alphabet, and the co-founder of Google’s Cloud documentation team. He’s worked for the past 14 years documenting an array of projects at Alphabet, including Kubernetes, App Engine, Adsense, Google’s data centers, and Google’s environmental sustainability efforts. He currently leads technical documentation at Waymo and mentors several junior writers in the industry.

Zachary Sarah CorleissenZach (he/him, they/them) began this book as the Lead Technical Writer for the Linux Foundation and ended it as Stripe’s first Staff Technical Writer. Zach served as co-chair for Kubernetes documentation from 2017 until 2021, and has worked on developer docs previously at GitHub, Rackspace, and several startups. They enjoy speaking at conferences and love to mentor writers and speakers of all abilities and backgrounds.

Jen LambourneJen (she/her) leads the technical writing and knowledge management discipline at Monzo Bank. Before her foray into fintech, she led a community of documentarians across the UK government as Head of Technical Writing at the Government Digital Service (GDS). Having moved from government to finance, she recognizes she’s drawn to creating inclusive and user-centered content in traditionally unfriendly industries. She likes using developer tools to manage docs, demystifying the writing process for engineers, mentoring junior writers, and presenting her adventures in documentation at conferences.

David NunezDavid (he/him) heads up the technical writing organization at Stripe, where he founded the internal documentation team and wrote for *Increment* magazine. Before Stripe, he founded and led the technical writing organization at Uber and held a documentation leadership role at Salesforce. Having led teams that have written about cloud, homegrown infrastructure, self-driving trucks, and economic infrastructure, he’s studied the many ways that technical documentation can shape the user experience. David also acts as an advisor for several startups in the knowledge platform space.

Heidi Waterhouse![../images/505277_1_En_BookFrontmatter_Figb_HTML.jpg](/api/v2/epubs/urn:orm:book:9781484272176/files/images/505277_1_En_BookFrontmatter_Figb_HTML.jpg)

Heidi (she/her) spent a couple decades at Microsoft, Dell Software, and many, many startups learning to communicate with and for developers. She currently works as a principal developer advocate at LaunchDarkly, but was reassured to find that technical communication is universal across all roles.
