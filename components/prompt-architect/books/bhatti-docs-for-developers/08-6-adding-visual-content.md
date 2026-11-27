© The Author(s), under exclusive license to APress Media, LLC, part of Springer Nature 2021J. Bhatti et al.Docs for Developershttps://doi.org/10.1007/978-1-4842-7217-6_6
# 6. Adding visual content

Jared Bhatti1, Zachary Sarah Corleissen2, Jen Lambourne3, David Nunez4 and Heidi Waterhouse5(1)Berkeley, CA, USA(2)Victoria, BC, Canada(3)Cornwall, UK(4)San Francisco, CA, USA(5)Mounds View, MN, USA
## Corg.ly: Worth a thousand words

*Charlotte looked at the comments Karthik had left on the draft. Some were easily fixable—a typo here, rearranging a paragraph there—but others would clearly need more work.*

*She spotted one comment in the overview she had written of Corg.ly architecture: “Not sure this describes data flow from the dog to the translation service to the user’s web application clearly. Is there more we can add or some other way to explain this?”*

![../images/505277_1_En_6_Chapter/505277_1_En_6_Figa_HTML.jpg](/api/v2/epubs/urn:orm:book:9781484272176/files/images/505277_1_En_6_Chapter/505277_1_En_6_Figa_HTML.jpg)

*She reread the section line by line. Having spent some time away from the draft, she immediately saw Karthik’s point. It didn’t look like there was information missing, but she could see how most users would struggle.*

*She looked back at the research she had compiled earlier in the planning stages. All users they had profiled were short on time and needed to quickly assess how Corg.ly would integrate with their product. Words weren’t enough; she needed to find another way to quickly show how easily someone could slot Corg.ly into their product. Maybe it was time for a diagram…*

## When words aren’t enough

Your brain is reading this sentence. And this one. You may think you’re consuming chunks of text, but your brain is actually processing each word in this sentence as a shape and connecting these shapes to concepts and ideas. We recognize these parts of words to understand the whole.[1](#Fn1) Although reading may seem fast, it can be an incredibly inefficient process.

You may have heard the phrase, “a picture is worth a thousand words.” How long would it take you to read a thousand words? More than 13 milliseconds? A human brain can process an image at that speed, and even if you flick your eyes to a new image immediately afterward, your brain will continue to process the first image for longer than you originally spent looking at it.[2](#Fn2)

Single images require less cognitive processing, help your brain draw connections, and derive understanding much more quickly than written text. We also remember information better if it’s presented alongside images. When you hear information, you’ll recall only approximately 10% of it. If that information is accompanied by an image, however, you’ll remember 65%.[3](#Fn3)

Effective visual content falls firmly in the high-risk and high-reward category of documentation. This chapter:- Helps you assess the risks and benefits of using visual content
- Gives you guidelines to create accessible additions to your documentation

## Why visual content is hard to create

Like written documentation, the most effective visual content is something the reader barely notices. It doesn’t require them to stop in order to think or be aware of the fact they are consuming anything at all. When visual content works, it conveys information so quickly that the reader sweeps through their task. In the words of Edward Tufte, statistician, pioneer of data visualization, and all-round visual content expert, “Graphical excellence is that which gives to the viewer the greatest numbers of ideas in the shortest time with the least ink in the smallest space.”[4](#Fn4)

Knowing how our brains process images and text helps us craft better content, down to the typography we choose. Your brain finds it easier to process simple unadorned typefaces because it can more easily recognize the curves and strokes of each letter like the ones used in a sans serif font. Reading UPPER CASE TEXT LIKE THIS is difficult because the letters are the same height and size. Variety helps comprehension.

In Chapter [3](505277_1_En_3_Chapter.xhtml), we discussed how using a variety of paragraphs, bullets, and numbered steps helps break up walls of text. Visual content is another way to bring variety to documentation and with great effect. In one study, readers who followed instructions with illustrations were 323% better at completing those instructions than readers with no illustrations to help.[5](#Fn5)

However, visual content is a supplement to and not a replacement for written documentation. Its purpose is to help increase understanding, and anything else is a distraction. “Every single pixel should testify directly to content,” says Tufte.[6](#Fn6)

If you’ve ever faced a set of architecture diagrams with too many arrows, labels, and layers, however, you know that visual content can quickly become more confusing than helpful. Visual content is often subjective. We often think we know what makes a good diagram or graphic helpful—but the most helpful visual content is what’s most useful for your reader. We know from Chapter [1](505277_1_En_1_Chapter.xhtml) on user research that what we as creators like is often different from what our readers need.

Ineffective visual content interferes with the transfer of information, usually due to a lack of:- Comprehension
- Accessibility
- Performance

It doesn’t matter whether you’re looking at screenshots, illustrations, graphs, videos, infographics, diagrams, or photographs. All visual content types, and all documentation including them, sometimes fail to help because of these issues.

### Comprehension

Eye tracking studies by the Nielsen Norman Group show readers pay closer attention to images that contain information relevant to them. Other images, however beautifully designed, are ignored.[7](#Fn7)

NoteYou might have been taught that different individuals learn better from different learning styles, for example, visual content over words. This has been debunked.[8](#Fn8) Well-designed visuals can help almost all readers.

That isn’t to say that aesthetics don’t play an important part in helping your reader. In fact, the opposite is true. Poor aesthetics can stop us from wanting to engage with content. “We react to design, and the aesthetics of the piece just as much as we react to the information contained in it,” says Julie Steele, co-author of *Beautiful Visualization.*[9](#Fn9)

An overcrowded diagram with crisscrossing arrows, missing labels, or different levels of abstraction is a hindrance, not just because they are confusing, but because they aren’t engaging to look at.

### Accessibility

We all need clear, helpful, visual content, but ineffective visual content further excludes readers with access needs. Someone using a screen reader cannot “read” an image without the addition of alternative text (“alt text”). Someone with color vision deficiency may find it hard to distinguish elements of an image if the color contrast between them is not high enough. Diagrams full of text, despite best intentions, may be unhelpful to dyslexic readers for whom visual content should provide a clear benefit.[10](#Fn10)

NoteIn the UK, 10% of the population is dyslexic. In the United States, an estimated 5–15% of the population is dyslexic.

### Performance

It’s easy to get caught up in the design of visual content, but many creators don’t consider how they will serve the image or video to their readers. Not everyone reading your documentation will be doing so with a top-spec machine or high-speed Internet connection.

Large images are necessary when printing documentation but can affect loading speeds online. Although it’s important to make your images large and clear enough for someone to zoom in, or use a screen magnifier, they shouldn’t be so big as to stop someone from being able to load them in the first place.

Now we know what to avoid, how do we apply these lessons to create valuable, understandable, accessible, and high-performing content?

## Using screenshots

Screenshots can be a useful addition to documentation, particularly to show a user interface (UI). If you think a screenshot would be useful to your readers, make sure they:- Never appear without introduction or reference in the text.
- Appear close to the instructions or related text.
- Are clean and clutter free—do not include anything in your screenshot not part of your UI.
- Include all relevant parts of the UI with enough context to reassure the reader they’re on the right screen.
- Not too big—your readers need to be able to read all parts of the image.
- Not too small—your readers need to be able to correlate the screenshot to the UI they experience.

It’s sometimes useful to annotate screenshots to draw your readers’ attention to parts of the image. Blocks and arrows can help highlight parts of the image. Graying out other areas can help de-emphasize them.

You may be familiar with the options for alternative (or “alt”) text on images, including screenshots. Screen readers will read all of the findable text on a page. Writing alt text is one way to make your content more accessible to screen readers.

A better practice is to include a full description of what the image shows within the body of your main text. Leaving alt text blank tells screen readers to ignore the image. Instead, add a description of the content of the image as if the image wasn’t there at all. For example, “there is a small cog at the top of the menu” rather than “an image of a small cog at the top of the menu.” If you find this tricky to write, try explaining the image out loud—how would you describe it to someone?

NoteThe W3C provides a useful “decision tree” to help you use alt text. [www.w3.org/WAI/tutorials/images/decision-tree/](http://www.w3.org/WAI/tutorials/images/decision-tree/)

Finally, never use screenshots as the sole source of critical information a reader may need, such as IP addresses or code samples. Readers often want to copy such samples or text for their own use and screenshots make that impossible.

## Common types of diagrams

Diagrams can be an effective way to convey complexity without resorting solely to words, especially for help with visualizing processes.

There are several types of process diagrams that are particularly helpful in documentation:- Boxes and arrows
- Flowcharts
- Swimlanes

### Boxes and arrows

Box and arrow diagrams depict a flow from one item to the next. They appear frequently for good reason. When used well, box and arrow diagrams clearly depict a relationship or data flow between entities that would be difficult to explain with text alone.

Start by writing down the entities and the relationships you want to express. For example:- *Database* ➤ *API* ➤ *Front-end* ➤ *User*

Choose a shape and line to denote each item and the relationship or flow you want to illustrate. Each entity should be represented consistently with a distinctive shape and design, for example, using square boxes exclusively to denote different apps (Figure 6-1).![../images/505277_1_En_6_Chapter/505277_1_En_6_Fig1_HTML.jpg](/api/v2/epubs/urn:orm:book:9781484272176/files/images/505277_1_En_6_Chapter/505277_1_En_6_Fig1_HTML.jpg)

*Figure 6-1Boxes and arrows can represent architecture*

Aim for minimal clutter. Do not cross any lines or arrows. Be clear whether a connecting line represents a one or two-way data flow, or whether it represents another relationship such as a dependency. If in doubt, add labels to the element or connecting line and add a legend that clearly defines what each element represents.

In Figure 6-2, the dotted lines and label help the reader understand which elements are microservices.![../images/505277_1_En_6_Chapter/505277_1_En_6_Fig2_HTML.jpg](/api/v2/epubs/urn:orm:book:9781484272176/files/images/505277_1_En_6_Chapter/505277_1_En_6_Fig2_HTML.jpg)

*Figure 6-2Box and arrows example of microservices architecture*

### Flowcharts

Flowcharts guide a user from a start to a finish point and are particularly helpful for documenting processes.

Write down the process in full if it’s not already included in your written draft. Consider all of the possible directions or steps someone could take to achieve a result. Knowing how many options you need to include will help you know how much space you’ll need.

As with all diagram types, it’s important to be consistent. Flowcharts often use the same shapes to denote a type of action (Figure 6-3). For example, rectangles indicate processes and diamonds indicate a decision point. Any text within shapes must be legible with a large and clear font.![../images/505277_1_En_6_Chapter/505277_1_En_6_Fig3_HTML.png](/api/v2/epubs/urn:orm:book:9781484272176/files/images/505277_1_En_6_Chapter/505277_1_En_6_Fig3_HTML.png)

*Figure 6-3Flowchart*

### Swimlanes

Swimlane diagrams  are particularly useful for situations with multiple contributors or acting parts. Much like a flowchart, they show a process from beginning to end. Each actor or contributor has its own lane, and each step of a process takes place in one of those lanes. In doing so, it’s easier to see at glance who or what is responsible for each step.

You can use horizontal or vertical lanes, or a mix of both. In Figure 6-4, each lane is a different “actor” in the flow. At each stage, the reader can see who performs which action.![../images/505277_1_En_6_Chapter/505277_1_En_6_Fig4_HTML.jpg](/api/v2/epubs/urn:orm:book:9781484272176/files/images/505277_1_En_6_Chapter/505277_1_En_6_Fig4_HTML.jpg)

*Figure 6-4Swimlane  diagram*

Use the same consistency in process shapes and flows as you would for a flowchart. Make sure any connecting lines are clearly separated from the swimlanes themselves and your horizontal or vertical swimlanes are clearly labeled.

## Drawing diagrams

Regardless of the type of diagram you choose, your objective is to simplify. Comic book artists have honed this skill. In his book, *Understanding Comics: The Invisible Art,* Scott McCloud explores how comics are incorrectly interpreted as conveying less information.[11](#Fn11) Instead, McCloud argues that by eliminating unnecessary detail, a comic’s true meaning is amplified. A good piece of art, or diagram, *guides* the user to understanding. To “simplify to amplify” as McCloud advises, you must keep your diagrams targeted to your users. Remember what you know about your audience and their task.

Illustrate only one idea per diagram. For example, show one level of abstraction in a system, one process flow, or a particular piece of logic. Figures 6-5 and 6-6 show the same process. The second is full of unnecessary detail that a reader may not need.![../images/505277_1_En_6_Chapter/505277_1_En_6_Fig5_HTML.jpg](/api/v2/epubs/urn:orm:book:9781484272176/files/images/505277_1_En_6_Chapter/505277_1_En_6_Fig5_HTML.jpg)

*Figure 6-5Simplified flowchart*

![../images/505277_1_En_6_Chapter/505277_1_En_6_Fig6_HTML.jpg](/api/v2/epubs/urn:orm:book:9781484272176/files/images/505277_1_En_6_Chapter/505277_1_En_6_Fig6_HTML.jpg)

*Figure 6-6Overly complicated flowchart*

It’s okay to use multiple diagrams where splitting the information keeps things simple. Think about ways to walk your reader through your system or process. Overview diagrams can be a helpful addition to conceptual documentation, especially for readers new to your product or domain. Lower-level diagrams detailing data flows between specific microservices may be more helpful for reference documentation. Splitting information into chunks or layers helps to keep your designs targeted and provide the appropriate level of information to a reader at different points of their learning.

### Start on paper

Like written documentation, effective diagrams start with good planning. Grab a whiteboard or pen and paper to sketch with. If you have lots of elements that will need a lot of space, try using sticky notes to represent components or processes. Physically sketching or moving sticky notes around can help group elements together and give you an opportunity to prototype different designs before getting into (often fiddly) tooling.

This can be a useful point for some rudimentary user testing. Show your sketch or sticky notes to someone else to see if their understanding matches yours. Are the entities and relationships clear? Are processes logical?

### Find a starting point for your reader

Consider where you want someone to begin reading your diagram. Make that starting point clearly identifiable, and consider the reading patterns of your users. For example, Western audiences tend to read from left to right and top to bottom, so the top left point of a diagram will be where a Western reader’s eyes are drawn to.

### Use labels

However neat your shapes and connecting lines, labels can help provide even more clarity. A good label can be strangely tricky! Labels must be legible (avoid tiny text) and understandable. However tempting it is to use an acronym to save space, your readers may not share your familiarity. If in doubt, spell it out.

### Use colors consistently

If you’ve used color to indicate a database, do not use it elsewhere in the diagram to indicate a microservice. Keep in mind some of your readers may struggle to distinguish colors. It’s best to avoid using color alone to convey meaning and instead make good use of labels.

NoteIf you’re concerned about how readable your text is on a colored background, use an online color contrast checker to make sure any colors have a contrast of at least 4.5:1.

### Place the diagram

The position of your diagram is equally important. Make sure it appears close to the instructions or description the diagram is helping to illustrate. Remember never to use a diagram in isolation and to write alt text consistent with the context in which the image appears.

### Publishing a diagram

Publish images in scalable vector graphic (SVG) format. Although other formats are available, SVGs scale well and ensure your reader can access and zoom in on your diagrams at any screen size.

### Get help with diagrams

Diagrams  can be hard! Luckily, there are experts and standards to help make your diagrams shine.

In the software world, Simon Brown’s C4 model is particularly handy for diagramming architecture. The model provides a standardized way of visualizing levels of abstraction. Brown’s second volume of software architecture for developer’s series covers the C4 model extensively.[12](#Fn12)

The Web Content Accessibility Guidelines (WCAG) provide extensive advice on making web content usable to all.[13](#Fn13) WCAG is equally as helpful for diagrams as for front-end development and design. A list of additional design resources is available in the Resources appendix.

## Creating video content

Beware anyone who tells you that videos are the solution to any software documentation problem. This isn’t to say that good video content cannot be a part of effective software documentation, but the path to success is littered with abandoned YouTube channels and footage of features last helpful to a user in 1998.

Video content can be useful when introducing a new concept. Marketers love it for the ability to condense an overview of a product or feature into a short time. Most technical writers are wary of videos. They are difficult to create, expensive to maintain, and most writers would struggle to prove they give value to users. Think about your readers: Would they really benefit from video overviews of your product? Could you provide a similar overview more quickly and cheaply with well-written documentation and some images?

If you do want to commit the time and money required for video production, find a professional. Video content is really, *really* hard to do well. Writing, filming, and editing video content always take longer than you expect, and you will need a professional’s expertise.

Much like static content, you must keep the accessibility of video to your readers in mind. Can all of your readers access the content using the hosting provider you have chosen? Is the video short enough to keep your readers engaged? Have you added captions to your video? Have you provided a full transcript with timestamps alongside the video? In addition to helping viewers who are deaf or hard of hearing, a published transcript can be indexed by search engines, making it more likely for your video to be found.

Remember that making changes to written or static images is much easier than amending a video. Plan ahead for your video maintenance: how long will it stay up to date? Are you prepared to reshoot or republish the video when you release a new feature?

## Reviewing visual content

Visual content, no matter how few words it contains, is still content. That means you need to subject it to the same editing process covered in Chapter [4](505277_1_En_4_Chapter.xhtml).

Never review the visual content in isolation. Check the text around it. Does its placement make sense in the text? Is it introduced properly? Does it move when you view your content on a mobile or larger screen and still make sense? Has it impacted your site’s performance?

Once you are satisfied it meets your comprehension, accessibility, and performance requirements, get it in front of colleagues for review. Remember that design is subjective and you still have the curse of knowledge. Your overfamiliarity with what you have documented makes it harder to evaluate your visual content objectively. In later chapters, we’ll explore ways to test the effectiveness of your documentation, including visual content.

## Maintaining visual content

Chapter [11](505277_1_En_11_Chapter.xhtml) discusses  the biggest reason for most documentation failures: maintenance. Written text can fall out of date fast, but visual content can fall even faster. A single UI change can render your screenshots obsolete. A quick process change can mean that a single line in a diagram suddenly guides users incorrectly. A new feature can make a very expensive and well-produced video almost worthless.

Regardless  of the format or tools you use to create an image, make sure you share the source files with others in order to make updates easy and possible.

## Summary

Visual content conveys information more quickly than text, but it’s tricky to get visual content right. Make sure your images and your text complement each other. Screenshots have numerous specific requirements to make them useful. Don’t substitute a screenshot for copy-pastable text. Diagrams, labels, and colors all benefit from consistency and clean practice.

Beware of video content! Its drawbacks almost always outweigh any advantages for small teams and small budgets. Keep the three principles of visual content fresh in your mind from design to maintenance:- **Comprehension**: Does this help my reader?
- **Accessibility**: Am I excluding any readers?
- **Performance**: Do this content’s size and format help or hinder my reader?

The next chapter guides you through taking the leap from creating and polishing content to putting a document out in the world for others to view.

Footnotes1Denis G. Pelli, Bart Farell, Deborah C. Moore, “The remarkable inefficiency of word recognition,” *Nature* (June: 2003), 423, 752–756.

2Potter M.C, Wyble B., Hagmann C.E, McCourt E.S, “Detecting meaning in RSVP at 13 ms per picture,” *Attention, Perception and Psychophysics* (December 2013).

3John Medina, *Brain rules: 12 principles for surviving and thriving at work, home and schoo*l (Seattle: Pear Press, 2008).

4Edward R. Tufte, *The visual display of quantitative information* (2001, 2nd ed.).

5W. Howard Levie and Richard Lentz, “Effects of text illustrations: A review of research,” *Educational Technology Research and Development,* 30, 195–232 (1982).

6Edward R Tufte, *The art of data visualisation*, PBS film, 2013.

7Jakob Nielsen, “Photos as Web Content,” Nielsen Norman Group, accessed June 26, 2021, [www.nngroup.com/articles/photos-as-web-content/](http://www.nngroup.com/articles/photos-as-web-content/).

8Calhoun, Ragowsky and Tallal, “Matching learning style to instructional method: Effects on comprehension,” *Journal of Educational Psychology,* Vol. 107 (2015).

9Julie Steele, *The art of data visualisation*, PBS film, 2013.

10David Roberts, “The power of images in teaching dyslexic students,” Loughborough University, accessed June 26, 2021, [https://blog.lboro.ac.uk/sbe/2017/06/30/teaching-dyslexic-students/](https://blog.lboro.ac.uk/sbe/2017/06/30/teaching-dyslexic-students/).

11Scott McCloud, *Understanding Comics: The Invisible Art* (New York: William Morrow Paperbacks, 1994).

12More information on the C4 model is available at [c4model.com](http://c4model.com).

13Web Content Accessibility Guidelines are available at [www.w3.org/WAI/](http://www.w3.org/WAI/).
