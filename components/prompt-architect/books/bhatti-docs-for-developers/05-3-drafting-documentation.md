© The Author(s), under exclusive license to APress Media, LLC, part of Springer Nature 2021J. Bhatti et al.Docs for Developershttps://doi.org/10.1007/978-1-4842-7217-6_3
# 3. Drafting documentation

Jared Bhatti1, Zachary Sarah Corleissen2, Jen Lambourne3, David Nunez4 and Heidi Waterhouse5(1)Berkeley, CA, USA(2)Victoria, BC, Canada(3)Cornwall, UK(4)San Francisco, CA, USA(5)Mounds View, MN, USA
## Corg.ly: First drafts

*Charlotte stared at the screen in front of her. The cursor blinked slowly. After all the research, all the planning, the writing should be the easy bit, right?*

![../images/505277_1_En_3_Chapter/505277_1_En_3_Figa_HTML.jpg](/api/v2/epubs/urn:orm:book:9781484272176/files/images/505277_1_En_3_Chapter/505277_1_En_3_Figa_HTML.jpg)

*She looked through the documentation plan again. She read the use cases and patterns they had identified and reminded herself of the user profiles they had drawn up just a week ago. As she read, her confidence began to build; the research and planning had answered so many of the hardest questions already.*

*Ein, curled under Charlotte’s desk, stretched and settled by her feet. Charlotte sat up a little straighter in her chair and began to type.*

## Confronting the blank page (or screen)

One of the hardest things about writing is confronting an empty document. There are so many things that you know about your code, but getting these thoughts down in clear, precise language for another person to understand can be mentally and emotionally difficult. Acknowledging that difficulty is the first step to working through it.

If you read through the previous chapters, you’ve already defined your audience, researched existing content and code, and chosen a documentation pattern to meet your users’ needs. This chapter is where you synthesize your work so far into content for your audience.

This chapter guides you through creating your first draft, while helping you:- Choose your writing tools
- Define your document’s audience and goals
- Craft an outline
- Use paragraphs, lists, and callouts to build your content
- Avoid getting stuck during your writing

## Setting yourself up for writing success

If you’re writing code on a regular basis, you probably spent a lot of time learning how to set up your coding environment in the way that works best for you: your preferred IDE, color themes, tools, and key bindings are things you experimented with until you found your comfort zone. Writing requires similar experiments and experience to find what’s right.

You may think that starting your document is a daunting task—but once you pick the right tools and compile the information you’ve already collected, you’ll have a good foundation for your document.

### Choosing your writing tools

When choosing your writing tools, consider two important factors: the format for your final content, and the shareability of drafts.

Most documentation you write will be published online, so your final format will likely be Markdown, HTML, or wikiscript. Any text editor can output in these formats, so there’s no need to learn a new set of tools. The same text editor you use for your code also works for your documentation.

It’s important to share drafts with others for reviews and feedback. You can use the same review tools you use for code to share and review your documentation. If you want to write your initial drafts in a word processor that allows you to easily share content and get feedback from others, that works too. Most word processors have plugins available that can convert your text into whatever markup you need.

Use the tools you’re most comfortable with. There’s no need to learn an entirely new set of tools to write documentation. All of the tools you use to write code also work for writing docs. Mixing tools also works: if you like drafting outlines with pen and paper, or sketching them out on a whiteboard, use those methods to get started.

Don't get hung up on choosing tools. Most of the time, your existing workflow works great!

### Breaking through the blank page

In previous chapters, you created an audience definition, researched existing content and code, and chose a documentation pattern to meet your needs.

You can start your document by listing the information you’ve already gathered at the top:- Audience
- Purpose
- Pattern

For example, let’s say you’re creating a document for a Corg.ly API that takes audio files of dog barks and translates them into strings of human language. You want to create a document that describes how to upload files to the Corg.ly service. Your initial information might look like:- Audience: Developers using Corg.ly who know how to use REST APIs
- Purpose: Describe how to upload audio files to the Corg.ly service for analysis
- Content pattern: Procedural guide

### Defining your document’s title and goal

You can define your document’s title based on the audience, purpose, and content pattern for the document. The title should be the shortest, clearest rephrasing of the document’s purpose from the user’s perspective.

In the example of the Corg.ly service, the purpose of the document is: *Describe how to upload audio files to the Corg.ly service for analysis*. You can shorten this further for the reader into something like: “Uploading Audio Files to Corg.ly”.

The title of the document should summarize the goal for reading the document. Anyone who clicks on your document title will know exactly what they’re getting. Here are a few examples of titles for additional documents:- Translating dog barks to text
- Translating dog barks from streaming audio
- Audio encoding and sampling rates

The title “Translating dog barks to text” lets the reader know that they will be learning how to perform a specific task (translating) from one format (dog barks) to another (text). The reader understands that this document is a step-by-step procedure covering how to do the task.

Likewise, a reader seeing the title “Audio encoding and sampling rates” sees that it doesn’t start with a verb like “Translating”, so it doesn’t cover a specific task. Instead, the document covers the technical specifics for audio file encoding and sampling for “Corg.ly”. It’s likely a reference for understanding *how* Corg.ly processes and interprets audio files.

The goal of each of these documents is defined in the title. Limit your document to only one goal. If your document has several goals, you probably need multiple documents.

## Creating your outline

Now that you’ve defined your title with the goal for your reader, consider all the steps that your reader needs to reach that goal. Start writing down all of these steps, and don’t worry about whether or not it’s in the right order.

If the goal is to understand a particular technical concept, write down all the parts that make up that concept. If the goal is to complete a technical task, write down all of the subtasks the reader needs to complete. If you made a friction log as part of your research, this is a good time to review it.

These initial steps form the *outline* of your document. An outline is a quick way to verify your approach to a document. Think of an outline as the pseudocode of a document: it lets you discuss your content with other developers and potential users before you’ve sunk too much time into writing.

Continuing the earlier example, here are some of the subtasks for “Uploading Audio Files to Corg.ly”, in no particular order:- Install the Corg.ly application
- Upload audio files to Corg.ly (using the user interface and the API)
- Authenticate with the API
- Verify the upload worked

Each of these subtasks is a separate topic, and each topic is a reference point to expand later. None of those bullet points actually contains any instructions, but you can see how the different topics relate to each other, and where they fit in the sequence. You can start filling out details for each topic by adding more bullet points describing increasingly granular tasks, or you can rearrange your topics now. As you practice writing, you will discover the process that’s most natural for you.

### Meeting your reader’s expectations

Once you create a title, goal, and outline for your document, it’s time to think about the *flow of information* . Consider what your reader needs to know and do to successfully complete the goal you stated in the title. Imagine their expectations and knowledge, drawing upon the research you’ve already done. The order of information in your outline should meet your user’s expectations and needs. The knowledge your reader has is different from yours, and their experience with what you’ve built won’t be as extensive. It’s up to you to provide the reader with the right information at the right time. This is what’s meant by the flow of information.

Review the initial outline you’ve written. Rearrange the steps if needed, focusing on how best to help your readers. You can start by grouping tasks hierarchically, splitting up some of the tasks if you think they might be too complex, and grouping similar tasks together. Grouping and rearranging the outline also gives you a chance to spot any information you may have missed in your first pass.

For example, the following steps describe “Uploading Audio Files to Corg.ly”, based on the initial set of tasks. The steps for this procedural guide are grouped in the order a user performs them, with tasks for the Corg.ly app user interface (UI) and the Corg.ly API grouped separately.![../images/505277_1_En_3_Chapter/505277_1_En_3_Fig1_HTML.png](/api/v2/epubs/urn:orm:book:9781484272176/files/images/505277_1_En_3_Chapter/505277_1_En_3_Fig1_HTML.png)

*Figure 3-1Steps for uploading audio files to Corg.ly*

### Completing your outline

Review the outline for the document and consider your readers. Ask yourself the following questions:- Is there additional introductory or setup information that readers need to know?
- Are there steps that you’re skipping or that aren’t fully explained?
- Do the steps make sense in consecutive order?

For readers uploading an audio file to “Corg.ly”, they need to know the audio file requirements for the application. They need to know how to authenticate with the REST API in order to use it. They also want to verify that their file uploaded successfully. Add all of these items to the outline:![../images/505277_1_En_3_Chapter/505277_1_En_3_Fig2_HTML.png](/api/v2/epubs/urn:orm:book:9781484272176/files/images/505277_1_En_3_Chapter/505277_1_En_3_Fig2_HTML.png)

*Figure 3-2Adding items to the outline*

## Creating your draft

When you feel confident in your outline, start drafting your content. That might feel intimidating at first, but building from an outline to a draft doesn’t need to be difficult.

The focus of your draft is to take the reader through the topics described in your outline, expanding on each topic with the detailed information your reader needs. When filling in content, you can use *headers, paragraphs, procedures, lists*, and *callouts*. Each of these conveys information in different ways. Each has its advantages and disadvantages.

This book covers visual forms of information like code samples, tables, diagrams, and graphics in Chapters [5](505277_1_En_5_Chapter.xhtml) and [6](505277_1_En_6_Chapter.xhtml).

### Headers

Headings  are like signposts: they organize content within your document. Headings also serve as destinations in documentation, letting readers jump to exactly the information they need. Headings help structure content for the reader, but they’re also important for search engine optimization (SEO). Make sure to include headings in your document.

You can create document headings from your outline by making each of the high-level steps in your outline a header. When creating headers, keep the following tips in mind:- **Be as brief, clear, and specific as possible.** Readers must be able to skim your headers quickly and understand your document at a high level.
- **Lead with the most important information.** Start with the most important information that readers need to know as close to the top of the page as possible.
- **Use unique headers for each section.** Unique headers help your reader find the right content quickly. For example, if there are multiple “testing” sections in the document, specify in the header what is being tested.
- **Be consistent.** Structure all of your headers similarly. If your document is a procedure for accomplishing a task, start every header with a verb. If you’re writing your document for a larger documentation set, match the style of headers in other documents.

### Paragraphs

Paragraphs  are groups of sentences that help readers understand context, purpose, and details of your document. Paragraphs give context about when to run a procedure, or offer details about how a procedure works. Paragraphs can contain stories that make a concept easier to understand, or they may give readers historical information that affects how they proceed.

Of the different types of text you can put in your document, paragraphs contain the most information, but they’re the slowest to read and the hardest to skim. When writing paragraphs, give your readers the context they need to understand and act, but keep it short. Limit paragraphs to five sentences or fewer when possible. Short paragraphs are easier to read on mobile devices!

### Procedures

A procedure is a sequential set of actions a reader takes to achieve a desired result. Procedures should always use numbered lists to help readers understand the order of tasks they’re performing. Explain the desired goal at the start of the procedure so that users understand what they are doing. At the end of the procedure, add a way for the user to check that they performed it correctly. This serves as a kind of unit test for the documentation, and prevents users from compounding any errors they may make.

For example, here’s a procedure to “Upload an audio file using Corg.ly’s UI”:1. 1.Open the Corg.ly app.
2. 2.Select “Record” to record your dog barking.
3. 3.Select “Upload” to upload your file for translation.

When you’re writing a procedure, identify the system’s starting state. Do you expect a reader to be logged in? Are they typing in a browser or a command line? Also, give readers the instructions they need to reach the desired state.

Each step of the procedure should only cover one action. Your reader may be jumping between your documentation and your interface or the command line, and multiple actions in a single step can make it hard for your reader to follow along.

Finally, give readers a way to verify they’ve completed the procedure properly. For example, at the end of the Corg.ly procedure, you could tell the reader they will receive a confirmation message if their upload has been successful.

### Lists

Listsallow you to group related information in a skimmable format. Lists include things like:- Lists of examples
- Settings
- Related topics

Lists are not in procedural order, but that doesn’t mean they are completely unordered. When creating a list, consider ordering it in a way that is most helpful to the user. For example, you could add a bulleted list to the audio file upload procedure:![../images/505277_1_En_3_Chapter/505277_1_En_3_Fig3_HTML.png](/api/v2/epubs/urn:orm:book:9781484272176/files/images/505277_1_En_3_Chapter/505277_1_En_3_Fig3_HTML.png)

*Figure 3-3Sample list of audio file types*

For a list of file types like this, you can order from most commonly used to least commonly used by your user. Alternatively, you could list it in alphabetical order, since that’s easy to skim.

The longer a list grows, the less skimmable it becomes. If you find yourself listing more than ten items, consider dividing the list into smaller lists, broken up by headers and paragraphs.

### Callouts

When writing your document, you might discover a piece of information that your reader needs to know at that moment, but that doesn’t fit with the flow of your content. It might be something absolutely critical that a reader needs to know in order to be safe, or it might be some useful, related information that you want to highlight at that point in the document. In these cases, you can use a *callout*  .

Here are some examples of callouts and when to use them:- **Warning:** Don’t take this action! Readers might be in danger, personal data might be at stake, or the system may suffer irreversible damage or loss.
- **Caution:** Proceed carefully. An action might have unexpected consequences.
- **Note:** Related information or a tip about what you’re currently reading.

Callouts  break the flow of your document, which is useful for highlighting scenarios for readers to avoid. Use color, icons, and other signals to highlight the severity of the callout, and make sure readers can see the callout before they take the related action.

For example, here’s a callout that you might find at the top of the doc for uploading an audio file to Corg.ly:![../images/505277_1_En_3_Chapter/505277_1_En_3_Fig4_HTML.jpg](/api/v2/epubs/urn:orm:book:9781484272176/files/images/505277_1_En_3_Chapter/505277_1_En_3_Fig4_HTML.jpg)

*Figure 3-4Example of a Caution callout*

Just as you may experience alert fatigue if you are bombarded with system alerts, your reader can feel the same if you use too many callouts. Reserve callouts for important information your readers cannot afford to miss.

Referring back to your friction log created in Chapter [1](505277_1_En_1_Chapter.xhtml) can be a great way to know where a note or a warning may be helpful to your reader.

## Writing for skimming

There are two fundamental, paradoxical truths about readers of technical documentation:- Readers come to your documentation looking for information.
- Readers read very little of what you write.

Think of how you read most content online: you probably search for something specific to catch your eye, quickly scanning the first few sections of multiple pages until you find what you’re looking for. Only when you’ve found what you’re looking for do you settle in and read content closely. You’ve moved through a number of pages while reading very little.

Most people read in the same way: skimming titles and headings until they find the content that answers their question. In fact, based on the time readers spend on a page, they can read at most 28% of the words on a page (and that’s if they’re a very fast reader)[1](#Fn1). This is true both for readers visually skimming through the document and for those using screen readers (tools that render content as speech or braille).

NoteWhen readers view a page of content, research shows they typically skim the content in an “F” pattern, scanning in two horizontal lines across the top of the document for the title and subtitle, and then scanning down the page. They do not read every word on the page.

Write in a way that helps your reader skim your content to find the right piece of information. Helping your reader skim helps them find the content they’re looking for faster, and it leads to better, more direct content. There are a number of strategies you can use to make your content more skimmable and therefore more helpful to your readers.

### State your most important information first

If your reader is skimming your document they will, at most, get through the first few paragraphs of your document. In those first paragraphs, it’s important that you answer the question that’s burning in your reader’s mind: “Will this help me?”

Your title should summarize the goal of the document. Include any critical information in the first three paragraphs. If you’re writing a procedure, let the reader know *what* they will accomplish by the end of the document. If you’re writing something more conceptual, explain the importance of the concept you’re describing, and *why* knowing more about it will help your reader.

### Break up large blocks of text

Long paragraphs are difficult to skim. If most of your writing is for print publications or academic papers, you’re probably more familiar with writing long-form essays. Unfortunately, most of your readers will skip over your page if they see a wall of text.

Instead, make long sets of paragraphs easier to scan by breaking them up with subheaders, lists, code samples, or graphics. Chapters [5](505277_1_En_5_Chapter.xhtml) and [6](505277_1_En_6_Chapter.xhtml) cover how to use code samples and visual content to break up your text.

### Break up long documents

It might be tempting to heap all of your content into a single document—but a single long document often tries to accomplish too many goals for too many different readers. Take, for example, the outline in Figure 3-5 for “Uploading Audio Files to Corg.ly”:![../images/505277_1_En_3_Chapter/505277_1_En_3_Fig5_HTML.png](/api/v2/epubs/urn:orm:book:9781484272176/files/images/505277_1_En_3_Chapter/505277_1_En_3_Fig5_HTML.png)

*Figure 3-5This outline tries to meet too many different goals*

The readers using the application to upload audio files to Corg.ly have a different level of technical knowledge and different needs than readers who use the API. As illustrated in Figure 3-6, it makes sense to break up this document into two and then further divide into topics.![../images/505277_1_En_3_Chapter/505277_1_En_3_Fig6_HTML.png](/api/v2/epubs/urn:orm:book:9781484272176/files/images/505277_1_En_3_Chapter/505277_1_En_3_Fig6_HTML.png)

*Figure 3-6Breaking apart an outline into two documents*

If breaking up a document by audience doesn’t work, experiment with other ways to break up the document. Can you break it up by type of information? By product feature used? By the format of content?

### Strive for simplicity and clarity

Short, concise documents are beautiful.

As you draft a document, ask yourself: “Does this content satisfy my reader’s needs?” It might be tempting to add information like the history of a project or the design considerations you’ve made on a system, but they don’t belong in a procedural document. Put the history, design theory, and commentary for a document in a separate place and title and format it appropriately.

## Getting unstuck

Every writer gets stuck. Writing is difficult, creative work, and creative work is sometimes hard to sustain. It’s not because you’re bad at writing! Getting stuck is part of the writing process, whether it’s floundering in the initial steps of creating your outline or somewhere in the middle of completing your draft.

There are ways to get unstuck. See if you can figure out what’s stopping you: is it a fear of being wrong? Is it a lack of time to engage material deeply? Is it concern about the finished product not being good enough? Once you identify the reasons why you’re stalled, it’s easier to resolve and keep going.

The following sections are strategies to help you when you get stuck while drafting content.

### Let go of perfectionism

Your first draft of content shouldn’t be perfect—in fact, it doesn’t even have to be good. The goal of a first draft is to get all of the information down for your readers, not to craft a perfectly polished document ready for publication. (For information about polishing a document for publishing, see Chapter [4](505277_1_En_4_Chapter.xhtml).)

So relax. Release any notions of content perfection, stop worrying about grammar, and focus on getting your ideas down on the page. The first draft is a judgment-free zone.

### Ask for help

One of the best ways to get unstuck is to talk through your problem with another person. Ask someone to read what you’ve written so far and work through your outline of content with them. Talk through the issues that you’re having and where you’re stuck.

You can also ask someone to write some of the content while you look over their shoulder (or virtual shoulder if you’re able to share your screen) while you review. You can also ask a peer to review your content; see Chapter [4](505277_1_En_4_Chapter.xhtml).

### Highlight missing content

[TODO].

We’ve all left TODO comments in code, and the same thing happens in documentation. As you’re writing, you may not have all the information you need to write a section, or you may realize there’s an essential part missing.

When you notice a gap in content—that important information is missing—make a note of it and keep working on the parts you’re sure you can fill in. You can fill in the gap during a later round of revision or writing.

Don’t get hung up on trying to write a document correctly and in order the first time through. Like code, writing is an iterative process. Write what you know, see what’s missing, research it, and write the new things you know.

### Write out of sequence

You don’t have to write the first thing first. Sometimes, the first thing that people read—the introduction—is the last thing you write. Good introductions describe a document’s major themes, what readers will gain from reading the document, and why it matters. These topics aren’t always clear until you’re finished writing the steps or conceptual details that make up the body of the document.

At other times, you may want to write the procedure first; for example, if you just learned the procedure and want to make sure you remember it. After writing the procedure, you can then write any prerequisites and the expected outcome.

Write in whatever order works best for you. It’s easy to change your words and move them around as needed.

### Change your medium

If you’re still struggling to write, try changing the medium that you’re writing in. If your text editor isn’t working for you, switch to a different program or leave your computer entirely. Try jotting down your ideas on a piece of paper, or sketch them out on a whiteboard. Voice transcription is also an option if speaking feels more comfortable than writing.

The important thing is to experiment with a variety of mediums to see what works best for you.

## Working from templates

If you’re making several similar documents that share the same document pattern, it’s worth creating a *template*. Templates provide reliable ways to create consistent documentation and simplify creating future documents.

Templates create a consistent user experience. They make writing easier by letting you focus on content rather than structure.

A template is a stable document with placeholders for headers and content that provides consistent formatting for a related group of documents. For example, you might have a release note template with sections for new features, documentation changes, and a table for all the known and fixed bugs. Templates provide consistent style, format, and outline, even as individual documents based on the same template contain different content.

When creating a template, evaluate existing documents (whether your own or others’) and make an outline of the sections that need to remain consistent for your document and others like it.

For example, bug reports often need to contain the same information each time, so a bug report template is often useful.

Bug Template**Bug title**

**Environment**

- Including Device/OS, brower, and software versions

**Steps to reproduce**

1.

2.

3.

4.

5.

6.

7.

8.

9.

10.

11.

12.

**Expected result**

**Actual result**

**Screenshots/visuals**

NoteTemplated documents are easier to skim.[2](#Fn2) For example, it’s easier to scan for specific information in multiple bug reports if the bug reports share a common pattern of formatting and structure.

Not every kind of document needs a template. For example, it’s probably not worth templating documents with unique content, or that focus on context or story. The more common a type of document is, the more helpful a template becomes. In addition to bug reports, commonly templated documents include:- Procedural guides for similar apps
- API and integration references
- Release notes

Templates also work for small documents such as glossary entries and error messages, which contain highly predictable forms of writing.

For a list of online template resources you can borrow, see the Resources appendix.

## Finishing your first draft

Eventually, your draft document will be done: you’ve written down all the information your reader needs to reach your stated goal. To determine whether you’re done, ask yourself:- Does the headline summarize the document’s goal?
- Do headings adequately summarize the document?
- Does your draft address your reader's needs from start to finish?
- Does the flow of information make sense to your reader?
- Does the draft address any issues you found in your friction log?
- Does your draft correctly follow any documentation patterns or a template?
- Have you tested and verified that any and all procedures work?

If you can answer yes to all of the questions above, then your first draft is done. Finishing a draft doesn’t mean that the content is ready to publish, but it does mean you’ve reached a major milestone in writing: you’ve conveyed all of the necessary information for your reader to succeed.

## Summary

Set yourself up for writing success by choosing writing tools that you’re comfortable and familiar with. The tool chain that you use for writing code likely works great for documentation as well.

Start by defining the audience, purpose, and pattern of the document. The goal of the document should be the title of your document.

Create an outline for your document and flesh it out using headers, paragraphs, lists, and callouts. Fill in the details of your plan (see Chapter [2](505277_1_En_2_Chapter.xhtml)).

Readers will skim your document, so make information easy to find by stating the most important information first and breaking up content for your readers.

Create and use templates if you’re making multiple similar documents to create consistent documentation.

First drafts don’t have to be perfect, or even good. The next chapter talks about editing your content and transforming it from a first draft into a document ready to publish.

Footnotes1Jakob Nielsen, “F-shaped pattern for reading web content (original study),” Nielsen Norman Group, published Apr 16, 2006, [https://​www.​nngroup.​com/​articles/​f-shaped-pattern-reading-web-content-discovered/​](https://www.nngroup.com/articles/f-shaped-pattern-reading-web-content-discovered/).

2“Reading: Skimming or scanning,” BBC Teach, accessed September 17, 2021, [https://​www.​bbc.​co.​uk/​teach/​skillswise/​skimming-and-scanning/​zd39f4j](https://www.bbc.co.uk/teach/skillswise/skimming-and-scanning/zd39f4j/).
