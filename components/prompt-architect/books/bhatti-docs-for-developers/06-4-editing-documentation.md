© The Author(s), under exclusive license to APress Media, LLC, part of Springer Nature 2021J. Bhatti et al.Docs for Developershttps://doi.org/10.1007/978-1-4842-7217-6_4
# 4. Editing documentation

Jared Bhatti1, Zachary Sarah Corleissen2, Jen Lambourne3, David Nunez4 and Heidi Waterhouse5(1)Berkeley, CA, USA(2)Victoria, BC, Canada(3)Cornwall, UK(4)San Francisco, CA, USA(5)Mounds View, MN, USA
## Corg.ly: Editing content

*Karthik took a sip of coffee and read through Charlotte’s draft of content for Corg.ly one more time.*

![../images/505277_1_En_4_Chapter/505277_1_En_4_Figa_HTML.jpg](/api/v2/epubs/urn:orm:book:9781484272176/files/images/505277_1_En_4_Chapter/505277_1_En_4_Figa_HTML.jpg)

*To him, the instructions were fairly simple. He could walk through them in less than two minutes and get translations working. He’d done it multiple times with Ein when demonstrating how the system worked for potential customers. Now that he saw all the instructions written out, however, he realized he took for granted how much users had to understand in order to succeed.*

*The document for using the Corg.ly API was basically a long list of steps for authenticating with the API and uploading an audio file to be analyzed. He read through the steps again and thought about Mei, their first customer.*

*He thought about all the questions she would ask if she were looking at this document. “Which of these steps are required?” would probably be the first thing she’d ask, followed by, “How do I tweak these API calls for my purposes?”, and finally, “What are some common errors I’ll likely run into?”.*

*Karthik kept these questions in mind as he made comments on Charlotte’s draft. Really, this wasn’t too different from a regular code review: add more detail here, add additional headers there, fix this link, and add some next steps. He knew he would have at least another round of feedback with Charlotte before they showed it to Mei.*

## Editing to meet your user’s needs

The creative act of writing isn’t the same as the analytical act of reviewing and evaluating text. If drafting content is about getting all of your ideas down, editing is the process of looking at your documentation and making sure it’s meeting your users’ needs. Beyond grammar and readability, editing makes sure that text conveys information to your users in the clearest, fastest, and most helpful way possible.

Trying to write and edit at the same time is slower than doing each task separately. Ask anyone who has been stuck at the beginning of writing a document, writing and rewriting the first sentence over and over for hours. Separating writing from editing lets you separate the process of creation from the process of evaluation, reviewing what you wrote with a critical eye outside of trying to get it down in the first place.

Editing documentation is similar to validating, testing, and reviewing code. You need to validate code in different ways to make sure that it runs, that it does what you expect it to do, and that it doesn’t cause problems with other code. Just as you can have bugs in code that passes a linter perfectly, you can have grammatically perfect documentation that fails to help your users.

Like code reviews, editing is a collaborative process, where you share your content with others, test your assumptions, and gather feedback. This may feel vulnerable at first, but it’s also where the most learning happens. As you integrate the feedback you receive, you may see more elegant ways to approach the problem you’re documenting and write more effectively.

This chapter guides you through the process of editing documentation, including:- Understanding different approaches to editing
- Creating a standardized editing process
- Accepting and integrating editorial feedback

## Different approaches to editing

When editing your work, it’s useful to focus on a single aspect of the document that you’re trying to improve. For example, “Is all of the technical information in this document correct?”, or “Is this document structured well?”. Trying to focus on all the factors of good documentation at once is both overwhelming and slow. It’s faster to break down the editing process into a series of *passes*, with each pass focused on one aspect of a well-edited document.

Depending on your users and their needs, you may have different aspects that you focus on while editing your content. However, for most developer documentation, your editing passes should focus on:- Technical accuracy
- Completeness
- Structure
- Clarity and brevity

Editing in this order lets you start with what you, the developer, know best (technical accuracy) and work toward what your users want (a well-written document that addresses their needs).

When editing for each of these qualities, read the document like someone encountering this information for the first time. When you know a product or technology well, it’s easy to make assumptions about familiar material, glossing over crucial introductory information that new readers need. The editing process is a great time to fill in these gaps and add information that helps users succeed.

### Editing for technical accuracy

When editing for technical accuracy, you’re editing for the correctness of your content. You should be able to answer the following questions:- If someone follows these instructions, will they get the result you promised them?
- Is there any technical jargon or terms that might lead to confusion?
- Are code functions, parameters, and endpoints named and explained correctly?

If you’re documenting a step-by-step procedure, follow the instructions yourself and verify that the instructions work. If you support multiple operating systems and developer environments, verify that they work and document any variations required in the procedure. If you made a Friction Log (see Chapter [1](505277_1_En_1_Chapter.xhtml)), verify that you’ve documented any workarounds or issues you identified there.

For documentation that explains a technical concept, verify that you’ve explained the concept at the level your user needs. If there are disagreements in terminology, make them consistent. For example, if you’re editing a document and see “encryption” and “hashing” used interchangeably, you should clarify which one is correct. This might require reviewing content with other developers and getting consensus.

A technical accuracy pass is also when you should check if there are any major sources of failure, data loss, or injury you should warn your users about. Any issues that would cause a critical or unexpected failure should be called out with a warning.

### Editing for completeness

When editing for completeness, you’re verifying that your content contains all of the necessary information for your user to be successful. It’s where you verify that there are no gaps in your content and that any [TODO] or [TBD] left in your draft is filled in.

When editing for completeness, consider your user and how they might be using your software. If you’re developing on Linux, and they’re developing on a Mac, will your instructions still work? What if they’re not using the latest version of your software, but one that’s still supported—will there be any unexpected errors?

Similarly, if you know of a foreseeable expiration date for information, note any limitations clearly. For example, instructions on filling out a tax form might say, “These instructions only apply to the 2021 tax year.” If a document is relevant only to a specific version of your software, be sure to document your version limitations clearly.

Editing for completeness is a great time to involve a new reader. New readers often see the gaps in your explanations and instructions far more quickly than you do. Watching someone else work through the document for the first time lets you understand what you’ve assumed and left out. The friction logs of new readers may help confirm your own logs or add depth by highlighting other sources of friction. For more information about friction logs, see Chapter [1](505277_1_En_1_Chapter.xhtml).

Completeness  is not the same as telling people everything. It’s as easy to lose readers with too much information as it is with too little. Completeness ensures you have enough documentation to help people who need it and not so much that they can’t find what they’re looking for.

### Editing for structure

The first thing a person sees when they open a document is the title, the headers, and the table of contents. These first few words are some of the most important parts of your document, giving your readers a set of signposts that point the way to the information they want. When you’re editing for structure, you’re verifying that these signposts are correct and that it’s clear to a reader what this document is about and how the topic is broken down.

As you edit for structure, you’re trying to answer the following questions:- Is it clear from the title and headers what the document is about?
- Is the document organized in a consistent and logical way?
- Are there sections in this document that should be put in another document?
- If a template exists, does the document follow it?

NoteChapter [2](505277_1_En_2_Chapter.xhtml) covers planning for common formats and why people use them. Editing for structure is a good time to verify that you’re following your documentation plan.

Using a consistent, predictable structure for your documents means that people can navigate to the part that’s most relevant to them. For example, consider websites for recipes: some readers might be interested in the history of how a recipe was developed, while other readers may want to skip straight to the instructions. In this example, clearly signposting the “history” part of the write-up from the “recipe” part creates a predictable structure that allows different groups of readers to quickly find what they need.

In addition to signposting what a document contains, you should also verify that you’re pointing your readers to what they should do both before and after they read your content. Most people use search to find the information they need: if a user shows up to your page without reading anything else, will they have the right prerequisite skills and knowledge to understand your document?

Clearly state any prerequisite steps. For example, “You must be an administrator to complete these steps,” or “This document assumes you have finished configuring your API.”

Likewise, if there are common next steps or additional information that a reader might need after reading your document, you should list those links. These signposts let your user know where they are on their journey.

### Editing for clarity and brevity

When editing for clarity and brevity, you’re reviewing your document on a line-by-line basis for how easily understandable each sentence and paragraph is. Reword awkward phrases, remove any duplicate information, and cut unnecessary words. Think of editing for clarity and brevity as code refactoring for documentation.

Editing at this stage includes all the classic elements of editing language, correcting for grammar, tone, and conciseness. Tools like spelling and grammar checkers can perform some of this work, but you should also review your document in its entirety. As you read each section of your document, ask yourself the following:- Is this as clear as it can be?
- Are there terms used inconsistently that I should correct?
- Are there unnecessary words or phrases that I can cut?
- Are there any idioms, metaphors, or slang that could confuse readers?
- Am I using any biased language that should be avoided?

Make your content as short and to the point as possible. While you’re editing, you might find yourself cutting a lot of content. This is a good thing! It means your reader will get to the right information quickly, without having to scan through your document.

Public style guidesUsing a publically available style guide helps you standardize language and grammar decisions and lets you focus on style decisions that are specific to your organization, like your product and feature names. This book’s Resources appendix contains a list of widely used developer style guides.

## Creating an editing process

You could do all of the editing passes by yourself for everything you write—but that becomes exhausting over time. In addition, reviewing your document immediately after you write it isn’t as effective as giving yourself some distance and reviewing with a fresh mind. With both the time and work required to edit well, it’s best to share the editing load with others by creating an *editing process*. An editing process creates a set of common procedures and standards for review.

Creating an editing process is similar to creating a code review process, and it has similar benefits. An editing process speeds up the length of time it takes to edit a document, allowing someone with a fresh perspective to give you objective feedback. It also helps share knowledge across reviewers and helps establish standards across documentation within your team.

A typical editing process is shown in Figure 4-1.![../images/505277_1_En_4_Chapter/505277_1_En_4_Fig1_HTML.jpg](/api/v2/epubs/urn:orm:book:9781484272176/files/images/505277_1_En_4_Chapter/505277_1_En_4_Fig1_HTML.jpg)

*Figure 4-1Editing process flow*

### Reviewing your document first

The first step in any review process is editing the document yourself. Reading your own writing is sometimes emotionally difficult, in the same way it can be hard to watch yourself on video or listen to a recording of your voice. Everything seems different from the inside, and experiencing ourselves from the outside takes compassion and practice.

One way to make reviewing your own content easier is to use an editing checklist. An editing checklist helps keep you on track, reviewing what’s important without getting bogged down in trying to create a perfect sentence. A checklist might look something like this:- Title is short and specific
- Headers are logically ordered and consistent
- Purpose of document is explained in the first paragraph
- Procedures are tested and work
- Any technical concepts are explained or linked to
- Document follows structure from templates
- All links work
- Spelling and grammar checker has been run
- Graphics and images are clear and useful
- Any prerequisites and next steps are defined

You may need to tweak this checklist to suit your needs, depending on what you’re writing. In addition, you may want to limit the time you spend editing: it’s easy to get bogged down in refining details instead of proceeding to peer reviews.

### Requesting a peer review

Peer reviews  for documentation are similar to code reviews for code. You’re requesting that someone review your content and make sure it’s useful and relevant for your audience. In the introduction to this chapter, peer review is exactly what Karthik is doing for Charlotte.

In the same way that you may have felt uncertain or uncomfortable when reviewing your own document, reviewers may feel uncomfortable if they don’t know what kind of editing you want. Clear requests make it more likely that you’ll get useful feedback. Tell your reviewer what kind of feedback you’re looking for. Is it structural? Technical? For clarity and conciseness?

In addition to requesting specific feedback from your review, it’s important to specify how you’d like to receive your feedback. Do you prefer to receive marked up paper, inline comments, or sidebar notes in a shared document? In peer reviews, the goal is to reduce friction, so your reviewer can comment efficiently and you can incorporate feedback easily.

You can use the same system to review documentation that you use to review code—and you can use similar review loops to request peer review for a document. Working within existing code review systems lets you improve your documentation by minimizing the number of new tools for your reviewers to learn and adopt.

For a first draft review, you probably want a reviewer on your team who is familiar with the product or procedure you’re documenting, similar to how Karthik reviews Charlotte’s work. As you get closer to publication, you may want additional reviews from people who are more like your target audience, to make sure you’ve written what they need to understand .

### Requesting a technical review

In a perfect world, you would know every aspect of the technology you’re documenting. In reality, you need to verify your technical understanding with others. This is where technical reviews come in.

Technical reviews  are a specific type of peer review to add or confirm details from a technical expert on a particular topic. Technical reviews are particularly important when you’re documenting an integration of two or more technologies, where you might be an expert on one but not the other.

Take, for example, the work that Charlotte and Karthik are doing on Corg.ly. They might know all of the technology in dog bark translation software, but they might not know how to build a dog bark translator collar. If they started working on a document for connecting hardware to the Corg.ly API, they’d likely need a lot of help from another technical expert in that field.

It’s often faster to request a targeted, specific technical review from someone who is an expert than trying to research and learn that information yourself. There’s no shame in asking for help, especially when doing so leads to a stronger document and clearer understanding  for your readers.

## Receiving and integrating feedback

After you request and receive reviews, you’ll have a pile of scribbles, pull requests, and other notes on how people want your text changed. What’s next?

First, take a deep breath. Feedback about writing can feel personal. Remember that reviews are intended to help you improve your content, not to pick on you as a person. The goal of your document is to communicate knowledge effectively to your readers. Ultimately, reviews help you help your readers and get you closer to your goal.

NoteFrom one group of writers to another, you are almost certainly doing better than you think you are.

Next, go through each reviewer’s comments in turn. If you start with the person who sent in the most feedback, you’re likely to preemptively address feedback from subsequent reviews. If you try to incorporate all feedback simultaneously on a single item, you’re more likely to lose track of edits and progress while attempting to resolve contradictory advice.

You should consider each piece of feedback you receive—but that doesn’t mean you have to accept it! Not all suggestions are helpful or necessary, even though your reviewer offered feedback with good intentions. Whether or not you accept their feedback, it’s important to acknowledge a reviewer’s help. Likewise, don’t reject feedback out of hand. It’s important to review all feedback to understand your reviewers’ concerns and maximize your document’s quality.

If you do receive contradictory feedback, consider what helps your user the most. If you get a suggestion that you should have more technical details from one reviewer, while another reviewer argues for less, then consider this: what does a user using this doc need to know?

After you incorporate all your changes, you can request a second round of reviews to get additional feedback on the changes you made and verify that it’s what your reviewers expected. A follow-up review of specific changes is comparable to reviewing subsequent commits on a pull request.

## Giving good feedback

If you expect to get good feedback from your reviewers, it’s important to know how to give good feedback as well. Peer reviews work best when you approach them with a constructive mindset. You’re not fixing someone else’s mistakes; you’re adding to their understanding.

Consider the animation studio Pixar’s method of reviewing and critiquing work, where feedback on creative or technical work must follow a rule called plussing,1 which is:> You may only criticize an idea if you also add a constructive suggestion.

When using the plussing method of offering feedback, focus on the idea, not the person. For example, start by saying something like, “I found this part unclear,” rather than, “You got this wrong.”

Follow your critique with specific suggestions for improvement. Constructive suggestions provide additional context for what you think would solve the problem. This “adding on” is why Pixar called the system “plussing.” For documentation, it’s helpful to suggest a specific way to rewrite an awkward sentence or a poorly defined concept. The more specific you make your constructive suggestion, the better your feedback becomes—and the more you help your users.

If you’re adding a lot of constructive feedback, give the original writer time to consider your suggestions. People need time to receive, evaluate, and implement feedback. Don’t expect an immediate response, especially if there are multiple reviewers.

In short, to provide good feedback:- Focus on the idea, not the person
- Follow up with a constructive suggestion
- Allow the recipient time to react to your feedback

One more note about feedback: it’s okay to point out things you like! For example, an elegant explanation of a deeply technical concept is worth pointing out and celebrating. In addition, pointing out great writing makes it easier for others to emulate.

Finally, provide the kind of feedback that you would appreciate receiving. When it comes to giving, receiving, and learning from feedback, Norm Kerth stated it well in the Agile prime directive:- *Regardless of what we discover, we understand and truly believe that everyone did the best job they could, given what they knew at the time, their skills and abilities, the resources available, and the situation at hand.*[2](#Fn2)

## Summary

Editing documentation is like testing and refactoring your code and just as important.

Edit a document in multiple passes to narrow your focus and reduce complexity. Different passes include technical accuracy, completeness, structure, brevity, and clarity.

Peer reviews are an important part of learning to write better and teaching your peers about your work.

When receiving feedback, consider each item of feedback and decide whether to integrate it into your content. You don’t have to accept each piece of feedback, but you should consider it.

When giving feedback, follow the rule of plussing: only criticize an idea if you also add a constructive suggestion.

Give feedback about what you like!

The next chapter covers integrating code samples into your documentation.

Footnotes1Erin ‘Folleto’ Casali, “Pixar’s plussing technique of giving feedback,” Intense Minimalism, published June 24, 2015, [https://intenseminimalism.com/2015/pixars-plussing-technique-of-giving-feedback/](https://intenseminimalism.com/2015/pixars-plussing-technique-of-giving-feedback/).

2Norm Kerth, *Project Retrospectives: A Handbook for Team Review* (New York: Dorset House: 2001), Chap. [1](505277_1_En_1_Chapter.xhtml), Kindle.
