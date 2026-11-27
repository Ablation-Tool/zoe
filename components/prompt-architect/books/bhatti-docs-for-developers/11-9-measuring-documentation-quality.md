© The Author(s), under exclusive license to APress Media, LLC, part of Springer Nature 2021J. Bhatti et al.Docs for Developershttps://doi.org/10.1007/978-1-4842-7217-6_9
# 9. Measuring documentation quality

Jared Bhatti1, Zachary Sarah Corleissen2, Jen Lambourne3, David Nunez4 and Heidi Waterhouse5(1)Berkeley, CA, USA(2)Victoria, BC, Canada(3)Cornwall, UK(4)San Francisco, CA, USA(5)Mounds View, MN, USA
## Corg.ly: Tuesday after the launch

*Success! Charlotte and Karthik watched the number of Corg.ly API users increase. Mei had emailed earlier in the week with congratulations and some initial feedback on the documentation and code. The celebrations were over, and, more than anything, Charlotte felt an immense sense of relief and accomplishment.*

*Charlotte put her laptop on the ground and motioned Ein to come over. “See,” she said, pointing at her screen. “We had over one thousand new signups just this morning.”*

![../images/505277_1_En_9_Chapter/505277_1_En_9_Figa_HTML.jpg](/api/v2/epubs/urn:orm:book:9781484272176/files/images/505277_1_En_9_Chapter/505277_1_En_9_Figa_HTML.jpg)

*Ein sniffed at the screen and barked twice. “Treat! Treat!” Corg.ly translated.*

*Charlotte pulled a doggie biscuit out of the jar on her desk and held it out to Ein. As Ein crunched down on his biscuit, Charlotte ruminated on the success of Corg.ly. The number of users continued to grow, but how did Charlotte’s team know their docs were successful? They were getting plenty of issues opened against both the docs and the product, issues that her team were busy triaging and addressing, but was there a way to measure the quality of their docs?*

## Is my documentation any good?

Like Charlotte, once you’ve published a few documents, you may have questions like, “Is my documentation any good?” and “How can I be sure?”

You might be tempted to dive straight into all of the available metrics for your content. Everything from page and site analytics, search data, click-through metrics, satisfaction surveys, and text analysis is available to measure.

The more metrics you gather, the more you might feel adrift. The numbers can create an illusion of an answer. It’s easy to find yourself chasing more and more metrics without getting an answer to your initial question.

To help you, his chapter guides you through measuring your documentation quality, including:- Understanding documentation quality
- Creating a document analytics strategy
- Aligning metrics to quality
- Using clusters of metrics

## Understanding documentation quality

Before you can measure document quality, you must first define “quality.” Luckily, a group of writers and engineers at Google worked on this very question: they evaluated documentation quality with similar methods for evaluating code quality.1 The definition for documentation quality they created is very simple:> *A document is good when it fulfills its purpose.*

If a document is good when it fulfills its purpose, then what is its purpose? The purpose of your documentation should align with the purpose of your code: to drive specific user behavior and accomplish the goals of your organization. Lifting vocabulary directly from the field of software testing, the group broke down documentation quality into two fundamental categories:- **Functional quality**, which describes whether or not a document accomplishes its purpose or goal
- **Structural quality**, which describes whether a document is well written and well structured

Both functional quality and structural quality have many components. Understanding these components makes them easier to measure and evaluate.

### Functional quality

The functional quality of a document describes whether or not the document accomplishes the goal it sets out to achieve. It examines at a fundamental level whether or not the document *works.*

Functional quality is difficult to measure holistically, but it’s the more important metric because it more closely aligns with the document’s purpose. The functional quality of documentation can be broken down into the following categories:2- Accessible
- Purposeful
- Findable
- Accurate
- Complete

#### Accessible

Accessibility  is the most essential aspect of functional quality. If your readers can’t access and understand your content on a fundamental level, they won’t be able to accomplish their goals.

For documentation, accessibility includes language, reading level, and screen reader access.

One of the most important parts of accessibility is writing in the language of your readers. In the United States, for example, census records show that more than 300 languages are spoken within the country, and 8% of the population has limited English proficiency.[3](#Fn3)

Globally, the number of developers who are proficient in English is very high. For example, 80% of developers in the Ukraine possess an intermediate or higher level of English proficiency.[4](#Fn4) However, you can’t assume that all developers know English and that their proficiency level is advanced. Looking at the number of page views and what language your readers select when viewing your content can help you understand whether your documents are sufficiently accessible.

Reading level is another  way to measure the accessibility of your documentation. In general, technical documentation should be written to a tenth grade level, including titles, headers, and paragraphs. This helps your readers understand your content quickly and pushes you, the writer, to use clear language and avoid complex technical jargon.

There are several methods of measuring a document’s reading level, including Flesch-Kincaid Grade level, the Automated Readability Index, and the Coleman-Liau index. Each of these indexes uses sentence length and word length to estimate the minimum grade level a person would need to understand your writing. There are many free document parsers that can assess your content with these indexes and guide you to any necessary adjustments.

Some users require accessibility devices such as screen readers to read and understand your documentation. It’s important to use alt text for any graphics, diagrams, or visuals you use. Also, any videos that you link to should also be captioned and subtitled. For more information  on accessibility for visual elements, see Chapter [6](505277_1_En_6_Chapter.xhtml).

NoteVerifying accessibility for the visually impaired extends far beyond the text of your document to include page elements and visual design. The World Wide Web Consortium (W3C) offers a set of Web Content Accessibility Guidelines (WCAG) that you can use to validate the accessibility of your content.[5](#Fn5)

#### Purposeful

For a document to be useful, it must clearly state its purpose or goal and then work to fulfill it. Your document should, in both its title and first paragraph, state the purpose of the document and what it will help your reader accomplish. These goals should align with both the goals of your organization and the goals of your reader.

For example, let’s say Charlotte is creating a document to help developers get started with the Corg.ly API. First, the document title should explicitly be the goal of the document for the reader, something like “Getting started with the Corg.ly API.” Next, the document should explicitly state at the beginning what the document covers, such as “Authenticating with the Corg.ly API” and “Making your first Corg.ly API call.”

To measure the success of this document, Charlotte might simply check the amount of time it takes for a new user to get to their first Corg.ly API call. This measurement is called Time to Hello World (TTHW). Task completion isn’t a perfect measurement of purpose and understanding, but it does give you a good starting point for understanding how effective your document is.

NoteTime to Hello World (or TTHW) is the amount of time it takes a developer to author “Hello World” in a new programming language. The concept has been extended beyond programming languages to [APIs](https://en.wikipedia.org/wiki/Application_programming_interface), as a measure of how simple it is for a new developer to get a basic example working. Faster times correlate to easier adoption.[6](#Fn6)

#### Findable

Findability  is the measure of how easily your readers navigate to and through your content.

You might think of findability as something that exists outside of your documentation, something that can be fixed with a good site architecture and a good search engine. Although good site architecture helps (see Chapter [10](505277_1_En_10_Chapter.xhtml)), search engines can direct users to the wrong page within your site or miss your site entirely. Readers searching for the right content can be stymied if your content doesn’t have the keywords they expect or if there are many similar sites with similar content. Understanding what your users are searching for, standardizing on search keywords, and monitoring how users find and enter your site all help increase findability.

Once readers make it to your site, they might not land on the right page. As Mark Baker, the author of *Every Page is Page One*, writes, “The real findability problem is how to get readers from the wrong place deep within your content to the right place deep within your content.”[7](#Fn7) If findability within your content is poor, you might notice readers entering and leaving your site repeatedly as they try different search terms to get to the right document.

To address deep content navigation, each document should provide as much context as possible for a reader’s current location in your site content as a whole. Contextual location, linking between related documents, using clear document types (Chapter [2](505277_1_En_2_Chapter.xhtml)), and using a site architecture (Chapter [10](505277_1_En_10_Chapter.xhtml)) all help your reader navigate smoothly and efficiently to the content they need.

#### Accurate

Accuracy  is the measure of how correct and credible the content is in a document. A document with high accuracy has correct and up-to-date technical explanations of the code it’s describing, along with working code samples and command line examples. A document with low accuracy might have several issues filed against it (see Chapter [9](505277_1_En_9_Chapter.xhtml)) and might contain code samples that are broken or superseded by new versions of your product.

Low-accuracy documentation leads to user frustration, as well as a loss of trust in both your documentation and product. How often have you searched for an answer to a problem and found a promising document, only to find out that the solution didn’t work?

Testing code samples, commands, API calls, and any other examples you provide helps proactively address accuracy issues. It’s also possible to automate tests that verify any examples you put in your documentation. Monitoring and addressing user feedback quickly also helps to improve document accuracy.

#### Complete

A document is complete if it contains all of the information necessary for the reader to succeed. For a task-driven document, completeness means:1. 1.Listing all prerequisites that readers should follow.
2. 2.Documenting all tasks required to finish the task.
3. 3.Defining next steps the reader should take.

If the document is an overview of a technical concept, it’s complete when it describes every key aspect of the technology that a reader needs to know. If the document is a technical reference, like an API reference, it should contain every single command in the API.

### Structural quality

The structural quality of a document describes how well it’s written. This includes sentence, paragraph, and header structure, quality of language, and accuracy of grammar. Structural quality encapsulates how easy a document is to read.

This book uses the “three Cs” of good writing to define structural quality:- Clear
- Concise
- Consistent

#### Clear

Clarity  is the measure of how easy your document is to understand. For documentation, clarity refers to how easily your reader can take in the information you’ve provided them and how confident they are that they will succeed.

At a holistic level, clear documentation has:- Well-defined and well-ordered headers that break down a topic into logical sections
- Headers ordered chronologically for tasks and each step indicating the desired outcome
- Unambiguous results for each step in a process
- Steps organized in a way your readers understand
- Content that calls out any places where a reader might get stuck
- Definitions of any errors that users may encounter

On a sentence-by-sentence level, clear documentation avoids unnecessarily long words or jargon that your reader might not understand. If you have to use unfamiliar words, define them for your readers .

#### Concise

A good definition of concision (or conciseness) is *brief but comprehensive*. At a holistic level, a concise document contains only information that’s relevant to a reader and their goals. Remove anything that gets in the way of a reader’s understanding, and link to anything that is relevant but not immediately necessary.

At a sentence-by-sentence and word-by-word level, concise documentation contains only the necessary information needed by the reader and no more. That includes avoiding unnecessary words and unnecessary concepts.

As William Strunk Jr., author of *The Elements of Style* says, “A sentence should contain no unnecessary words, a paragraph no unnecessary sentences, for the same reason that a drawing should have no unnecessary lines and a machine no unnecessary parts.”[8](#Fn8)

NoteThere are several tools that can measure and improve the conciseness of your documentation, such as the Hemmingway Editor ([hemmingwayapp.​com](http://hemmingwayapp.com)). These tools evaluate your content to make it easier to read.[9](#Fn9)

#### Consistent

Document consistency  means that the structure of your content, the concepts that you introduce, and your word choice are the same throughout your documentation. At a holistic level, consistent documentation has consistent titles, headers, paragraph structures, and lists. The content uses patterns that a reader can easily follow and use to skim documentation and quickly find what they need.

On a sentence-by-sentence level, consistency means that the same terms mean the same thing. For example, if a user is authenticating with the Corg.ly API, it’s important to always call it “authenticating” and not use other terms like “Connecting to the Corg.ly API.” Keeping terms consistent in your documentation makes it easier for readers to understand your content quickly.

Using a style guide and a standard set of document types helps create content consistency.

### How functional and structural quality relate

Ideally, your documentation should have both high structural quality and high functional quality. However, functional quality is more important. A well-structured, well-written document that doesn’t accomplish its goal is a poor piece of documentation. A document with structural issues that still accomplishes its goal is a good document.

Here’s a good way to think about it:- Low functional quality + high structural quality = poor overall quality
- High functional quality + okay structural quality = good overall quality

When collecting metrics about your documentation, it’s easy to focus on structural quality instead of functional quality. Metrics for word count, time your users spend on a page, and consistency of language are easier to gather than whether or not a user is successful at accomplishing the documented task. That’s why before you begin collecting analytics, it’s important to first define what you’re looking to measure and improve.

## Creating a strategy for analytics

For documentation to be effective, it must align your technical and business goals with the goals of your reader. As stated at the beginning of the chapter, “*A document is good when it fulfills its purpose.”*

An analytics strategy helps you recognize how your documentation goals align with the larger goals of your readers and your organization. A strategy allows you to focus on the metrics that are important to what you want to improve while ignoring the rest.

To create an effective analytics strategy, clearly define the following:- Your organization’s goals and how they’re measured
- Your reader’s goals and how they’re measured
- Your documentation goals and how they’re measured

Your documentation should help readers accomplish their goals, which in turn help your larger organization accomplish its goals. These metrics should all align with one another, so it’s useful to look at all of these together.

Organizational goals and reader goals are covered in Chapter [1](505277_1_En_1_Chapter.xhtml), but as your set of documentation grows, and your documentation becomes more specialized, it’s useful to revisit these goals before starting to measure quality.

### Organizational goals and metrics

Organizational goals are specific behaviors the organization wants from its users. These goals are usually tied to revenue. They focus on increasing revenue through adding users, engagement, and retention. They can also focus on reducing costs by addressing support needs and customer questions at scale. These goals include things like:- Recruiting and onboarding new users
- Encouraging existing users to adopt new features
- Getting users to complete a specific task
- Retaining existing users
- Addressing users’ support needs and product questions

Referring back to Chapter [1](505277_1_En_1_Chapter.xhtml), Corg.ly’s goal was to *recruit and onboard new users to Corg.ly by helping them integrate with Corg.ly’s API*.

To be successful, Corg.ly needs to optimize these key behaviors from its users:- **Increase adoption of Corg.ly’s API by developers**: Adoption of Corg.ly’s API by other developers and device manufacturers is the fastest way for Corg.ly to scale. This is the highest margin activity for Corg.ly and the service on which they are focusing most of their engineering efforts.
- **Help Corg.ly API users integrate with the API**: Corg.ly needs to teach new developers how to use the Corg.ly API and features and retain them over the long term to maintain revenue.

In order for Corg.ly to succeed as both a technical platform and as a business, it must encourage users to engage in these behaviors. Therefore, when documentation is created for Corg.ly, it should align with goals listed in Table 9-1.Table 9-1Goals and metrics

| Organizational goal | Success metrics |
| --- | --- |
| Increase adoption of Corg.ly’s API by other developers | Increased sign-ups to use the APIIncreased usage of the APIDecreased number of support questions from API users |

### User goals and metrics

While the business goals of your organization are focused on revenue and adoption, your readers’ goals are focused on completing specific tasks. You already outlined these goals in Chapter [1](505277_1_En_1_Chapter.xhtml), when you were researching your readers’ needs. It’s useful to highlight them again as you’re considering documentation quality.

Your readers’ goals are smaller and more specific than your organizational goals. They can include things like “Downloading the SDK,” “Authenticating with your service,” or “Troubleshooting an Error.” They’re also more subjective in measurement.

When considering the documentation for using Corg.ly’s API, readers might have any of the following goals:- Get started using the Corg.ly API
- Authenticate with the API
- Send a dog bark to the API for translation
- Receive a translation in the form of a text
- Receive a translation as an audio file
- I received an error from the service and I need to fix it

Each one of these goals might have more than one document related to it and might have different metrics related to its success.

Using the Corg.ly example of “Getting started with the Corg.ly API,” your readers’ goals might include the following:- Sign up for the API
- Get access to the API
- Learn the basics of using the API

You can then align these with specific success metrics listed in Table 9-2.Table 9-2Goals and metrics

| Reader goals | Success metrics |
| --- | --- |
| Sign up for the APIGet access to the APILearn the basics of using the API | Increased sign-ups to use the APIIncreased requests for API accessIncreased numbers of active API users |

### Documentation goals and metrics

There are many different kinds of metrics you can gather from web analytics tools that can help you measure document quality.

Documentation metrics you can collect include:- **Unique visitors**: Unique visitors are the number of people who have visited your site over a set period of time.
- **Page views**: A page view records each time a visitor looks at a page. Page views help you understand which of your pages are visited most, least, or not at all.
- **Time on page**: Time on page tracks the amount of time a visitor spends on your page before moving on to the next one.
- **Bounce rate**: Bounce rate is the number of visitors who come to your site, visit one page, and then leave (“bounce”) without viewing other pages.
- **Search keyword analysis**: Keyword analysis shows you the search terms visitors use to enter your site. It can help you understand whether you’re providing the information your users are looking for.
- **Reading level or text complexity analysis**: Reading level or text complexity analysis helps you understand how difficult your pages are to read and understand.
- **Support issues related to documentation**: Tracking support issues related to documentation helps you understand where documentation fails to meet your user’s needs.
- **Link validation**: Link validation evaluates whether links to and from pages on your site are broken. Broken links are a common source of user frustration.
- **Time to Hello World (TTHW)**: Time to Hello World is the amount of time it takes a developer to author “Hello World” in a new programming language or to accomplish a fairly simple task with your service.

The available metrics are nearly inexhaustible, so it’s important to narrow down the metrics you’re looking at based on the scenario you want to measure. For example, to assess the quality of a set of docs for “Getting started with the Corg.ly API,” Table 9-3 lists some questions to ask and some metrics that could answer those questions.Table 9-3Questions of quality and associated metrics

| Questions | Document metrics |
| --- | --- |
| How many users are reading the docs? | Unique visits |
| Which docs are they looking at the most? | Page views |
| How long does it take a user to get started? | Time to Hello World (or in this case, “Time to getting started with the Corg.ly API”) |
| How are users finding the document? | Findability of the “Getting started with Corg.ly API” document, including search keywords, links, and inbound traffic |
| Are there problems with the document that need to be fixed? | Number of user issues filed against the documentLink validation |

The goal with these metrics is to answer the question, “Is the document fulfilling its purpose?” You can track additional metrics to better understand your readers and their behaviors, but make sure you’ve identified the core metrics that help you evaluate your documentation.

## Tips for using document metrics

There’s no one-size-fits-all approach to gathering and analyzing metrics on documentation. The metrics you can gather depend on where your content is published, what tools you have available to gather user data, and the amount of time you have to analyze your results.

When evaluating the quality of your content with documentation metrics, keep the following tips in mind:- Make a plan
- Establish a baseline
- Consider context
- Use clusters of metrics
- Mix qualitative and quantitative feedback

### Make a plan

Make a list of specific questions you want to answer about your content. In addition to what you want to measure, you should outline your rationale and how it will help you. Bob Watson, professor of technical communications, suggests that at the minimum, you should answer the following questions:10- Why do you want to measure?
- What will you do with the information?
- How will your effort advance the goals of your organization?

Knowing what you want to measure and why you want to measure it helps you focus your work and helps you to think through whether or not those metrics are worth pursuing.

### Establish a baseline

Once you select a set of metrics to track, you need to establish a baseline for those metrics. A baseline allows you to compare metrics before and after you’ve made changes so you can evaluate their impact. If you only take measurements after you’ve made your changes, you won’t have anything to compare them to!

### Consider context

Quantitative metrics  can be misleading if you consider them outside of a document’s context. Different documentation helps users accomplish different goals. Readers use documentation in different ways depending on their needs, which become visible in more contextual metrics.

For example, if page views increase for “Getting started with the Corg.ly API,” that’s a good thing. More users are interested in learning how to use Corg.ly. However, an increasing number of views for a page that describes Corg.ly error codes may mean readers are having problems with the product, the documentation, or both.

### Use clusters of metrics

A cluster of metrics can often give a better answer to a question than a single metric alone, especially if you can correlate relationships between those metrics. For example, let’s say that Corg.ly notices an increase in support issues for the Corg.ly API, so Karthik publishes a set of troubleshooting content for Corg.ly users. After publishing, the number of support issues continues to rise. Karthik could assume that the documentation wasn’t effective, but he couldn’t be 100% sure that’s correct.

It could be that Corg.ly has a huge influx of new users and there are more users filing fewer support cases. In this case, Karthik’s documentation is working. It could also be that users aren’t finding the content, so Karthik would need to improve the findability of the content. In this case, looking at a cluster of metrics would help Karthik solve this problem.

### Mix qualitative and quantitative feedback

When evaluating your content, it’s important to look at both quantitative and qualitative feedback. Page metrics, search analytics, and number of users are all relatively easy to track, so it’s easy to focus on these hard numbers. However, qualitative feedback from user studies, support issues, and user feedback can provide more context on specific issues you can fix to improve your documentation.

## Summary

A document is good when it fulfills its purpose. When considering and measuring document quality, consider functional quality (how well the document fulfills its purpose) and structural quality (how well written the document is).

When measuring your documentation, make sure your goals for your readers and your organization align.

Create a plan for measuring your documentation, establishing a baseline for metrics, evaluating usage patterns in context, using clusters of metrics, and considering both quantitative and qualitative feedback.

The next chapter covers information architecture: how to organize your content to make it searchable and easy to navigate.

Footnotes1Riona Macnamara et al. “Do Docs Better: Integrating Documentation into the Engineering Workflow” in *Seeking SRE*, ed. David Blank-Edleman (O’Reilly Press, 2018).

2Torrey Podmajersky, *Strategic writing for UX: Drive Engagement, Conversion, and Retention with Every Word*, pp. 113–115 (O’Reilly, 2019).

3“The Limited English Proficient Population in the United States in 2013,” Jie Zong and Jeanne Batalova, Migration Policy Institute, published July 8, 2015, [www.migrationpolicy.org/article/limited-english-proficient-population-united-states-2013](http://www.migrationpolicy.org/article/limited-english-proficient-population-united-states-2013).

4“How Many Software Developers Are in the US and the World?” DAXX, published February 9, 2020. Retrieved from: [www.daxx.com/blog/development-trends/number-software-developers-world](http://www.daxx.com/blog/development-trends/number-software-developers-world).

5Web Accessibility Initiative (WAI): Making the Web Accessible, accessed June 27, 2021, [www.w3.org/WAI/](http://www.w3.org/WAI/).

6Brenda Jin, Saurabh Sahni, Amir Shevat, *Designing Web APIs: Building APIs That Developers Love* (O’Reilly Media, 2018).

7“Findability is a Content Problem, not a Search Problem” Mark Baker, *Every Page is Page One,* published May 2013, [https://everypageispageone.com/2013/05/28/findability-is-a-content-problem-not-a-search-problem/](https://everypageispageone.com/2013/05/28/findability-is-a-content-problem-not-a-search-problem/).

8William Strunk, *The Elements of Style*. 4th ed. (Pearson, 1999).

9Hemingway Editor, [www.hemingwayapp.com/](http://www.hemingwayapp.com/).

10“Measuring your technical content – Part 1” Bob Watson, Docs by Design, published August 24, 2017, [https://docsbydesign.com/2017/08/24/measuring-your-technical-content-part-1/](https://docsbydesign.com/2017/08/24/measuring-your-technical-content-part-1/).
