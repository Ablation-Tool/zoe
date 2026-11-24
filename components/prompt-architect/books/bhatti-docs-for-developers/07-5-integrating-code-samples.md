© The Author(s), under exclusive license to APress Media, LLC, part of Springer Nature 2021J. Bhatti et al.Docs for Developershttps://doi.org/10.1007/978-1-4842-7217-6_5
# 5. Integrating code samples

Jared Bhatti1, Zachary Sarah Corleissen2, Jen Lambourne3, David Nunez4 and Heidi Waterhouse5(1)Berkeley, CA, USA(2)Victoria, BC, Canada(3)Cornwall, UK(4)San Francisco, CA, USA(5)Mounds View, MN, USA
## Corg.ly: Showing how it works

Charlotte looked through her draft and the feedback from Karthik. Most edits had been straightforward: fixing a typo here and slightly restructuring the text there. Karthik’s other comments could be grouped into two questions:- *How can we explain this better?*
- *What does this look like in practice?*

![../images/505277_1_En_5_Chapter/505277_1_En_5_Figa_HTML.jpg](/api/v2/epubs/urn:orm:book:9781484272176/files/images/505277_1_En_5_Chapter/505277_1_En_5_Figa_HTML.jpg)

*Charlotte knew from her team’s early research that Corg.ly users wanted to see the product in action. While product demos were on the team’s roadmap, code samples could show developers how Corg.ly worked in practice and with far fewer words. The API was fundamental to developers building integrations with Corg.ly, and the reference documentation was the perfect place to show example requests and responses.*

*With this realization, Charlotte scrolled to the top of the draft and began marking where code samples could help.*

## Using code samples

> *Code is in another language, so as much as you might try to describe the communication in this other language through text, it often falls short. When developers see code, they can often read the code and understand it natively.*[1](#Fn1)

> —Tom Johnson, I’d Rather Be Writing

Code samples are a critical part of effective developer documentation. Text and code are different languages, and it is code that your reader ultimately cares about.[2](#Fn2) No matter how clear or beautifully articulated your words, nothing beats a well-crafted code sample to help your readers get started or to demonstrate how to use a particular feature. A good sample can say more than the prose that describes it while providing a useful frame of reference for your readers to build upon.

Research from Twilio’s documentation team showed that when developers were trying to accomplish a specific task with their product, they specifically sought out pages with code samples and ranked them higher. Furthermore, they skimmed over any introductory text while hunting for code embedded in the docs.[3](#Fn3) You may have done the same while reading this book!

If code samples are the gold your readers are hunting for, then samples need to be specific, useful, and maintainable. This chapter covers:- Types of code samples
- Principles of good samples
- Designing useful code samples
- Generating samples from the source code

## Types of code samples

In general, documentation contains two types of code samples: *executable* and *explanatory.*

Executable code is runnable: code that your readers can copy and paste, perhaps after personalizing the example. For example, the request to the Corg.ly API in Listing 5-1 retrieves information about a specific bark. The code samples throughout this chapter assume that the Corg.ly team writes their documentation in Markdown.4Example request:```shell$ curl 'https://corgly.example.com/api/v1/bark/1' -i```Listing 5-1Sample API request

Explanatory code isn’t expected to be runnable. It’s usually an output or a block of code that a reader can learn from or compare to their own. Readers expect that explanatory code samples, especially outputs, match what readers experience in their own environment. Readers also expect that copying and pasting an output or error code into site search produces relevant results with no ambiguity.

Consider an example response in API docs (Listing [5-2](#PC2)).

Example response:```{  "id": 1,  "name": "woof",  "created": "2021-02-22T14:56:29.000Z",  "updated": "2021-02-29T17:56:28.000Z",  "tags": [    "happy",    "anxious",    "hungry"  ]}```Listing 5-2Sample API response

## Principles of good code samples

Like good documentation, readers expect your code samples to just work. Readers want to be able to skim through your documentation, find a code sample, grasp the concept demonstrated in the sample, and copy and paste the code if applicable. They also want this code to always be up to date and production-ready.

With these sorts of expectations, it takes considerable effort to make something “just work,” and there are several principles to keep in mind. A good code sample should be:- **Explained**: It’s displayed alongside a written description, whether in the main body of text or in code comments to provide context and explanation where needed.
- **Concise**: It provides the exact amount of information needed by the reader.
- **Clear**: It follows conventions a reader would expect of the language the sample is written in.

Executable code should also be:- **Usable (and extensible)**: It’s clear how the reader uses the sample and where they need to input their own data.
- **Trustworthy**: It’s pastable, works, and only does what a reader expects.

### Explained

Explanations that accompany your samples are as important as the samples themselves.[5](#Fn5) Even the cleverest of code samples need your writing skills to provide your readers with context.

Your documentation should explain any prerequisites to running a code sample, like installing any specific libraries or setting environment variables. Describe any limitations to the code, for example, if the code only runs with certain versions of a programming language.

Introduce code samples with a clear explanation so that your readers know what to expect if they run or encounter this code. Specifically, your explanation shouldn’t be a description of *what* it does, but *why* it does it. Really useful code samples explain anything that’s unique to your software, for example, an odd naming convention or particular method.

If the sample immediately follows an instruction or explanatory line, end the line with a colon (Listing [5-3](#PC3)).

The response you receive from the Corg.ly API should look similar to the following:```{  "id": 1,  "name": "woof",  "created": "2021-02-22T14:56:29.000Z",  "updated": "2021-02-29T17:56:28.000Z",  "tags": [    "happy",    "anxious",    "hungry"  ]}```Listing 5-3When instructions or explanations precede code samples,  end them with a colon

If you provide a sample input, follow it with a description or sample of a successful output that matches what your users would see.

If you’re documenting an API, match the sample request and parameters to the exact response a reader would receive with those same parameters (Listing 5-4).HTTP method and URL:```shell$ curl 'https://corgly.example.com/api/v1/translate' -i -X POST \  -H 'Content-Type: application/json' \  -d '{"query": "woof woof arf woof"}'```Response:```http requestHTTP/1.1 200 OKContent-Length: 456Content-Type: application/json{"meta": {"total": 5},"data": [{"translation": "It's so good to see you!","confidence": 0.99},{"translation": "Play with me!","confidence": 0.90},{"translation": "I am ready for my walk, please","confidence": 0.76},{"translation": "I am hungry","confidence": 0.60},{"translation": "I need a nap","confidence": 0.51}]}```Listing 5-4Match sample requests to exact outputs

Include samples of any common errors that users might experience. Make sure samples match actual outputs.

For more complex code or lengthier samples, consider including inline comments with executable code. If you use comments to break up larger samples, keep comments short and to the point. Use comments to explain the intent behind the code, explaining the “why” that may be missing to someone reading your code for the first time.

If you find yourself writing lengthy explanations, consider whether the code needs to be less complex to make a good sample. If you can, refactor the code into a simpler sample. Otherwise, talk with the engineers for the product, and let them know that a particular use case requires elaborate interaction with the code base and could be a source of confusion.

### Concise

Making code samples concise doesn’t just mean making them shorter. It means making sure your samples convey the essential information users need to complete their task, and nothing else. Keep your sample focused on the specific use case you’re trying to highlight, without adding anything unnecessary. It should only show the features you are documenting at that point.

Irrelevant code or overly complicated examples can confuse your reader and make it difficult to see the intention of your code. It also makes it harder for readers to copy and paste your code and modify it for their own purposes.

NoteKeep code sample lines short enough to display fully at default screen widths. Horizontal scroll bars are awkward!

Sometimes, larger samples are more helpful to a reader but can be more difficult to read. Help your users by breaking up those larger chunks (Listing 5-5).- Wrap lines after a number of characters (Google’s style guide suggests 80)
- Use an ellipsis (...) to indicate where you aren’t showing the whole sample

Response:```http requestHTTP/1.1 200 OKContent-Length: 456Content-Type: application/json{"meta": {"total": 5},"data": [{"translation": "It's so good to see you!","confidence": 0.99},...{"translation": "I need a nap","confidence": 0.51}]}```Listing 5-5Wrap lines at 80 characters and mark gaps with ellipses

### Clear

You may need to refactor your code in order to make a good sample. In the process of documenting your software, you may find all sorts of shortcuts and scrappy code you wrote in order to ship a change. That may be helpful to you, but can be confusing for a reader.

Consider what a reader needs from each sample and edit accordingly. For example:- Use descriptive class, method, and variable names in your code that your readers will understand.
- Avoid confusing your readers with hard-to-decipher programming tricks, unnecessary complexity, and deeply nested code.
- Omit any aliases that have made their way into your documentation unless they’re required and you’re certain readers will have the same aliases.

In addition, follow any existing code style conventions for your language or project. Some large open source projects create their own style conventions, as do most languages. Following existing style guides creates less cognitive overhead for your readers. The result should be clear, readable, and consistent samples so your reader ends up using code that already follows best practices.

### Usable (and extensible)

Part of the delight of a well-crafted code sample is the amount of time a reader can save by copying and pasting. However, a reader often needs to replace some data in order to make it applicable for them. It’s important that a reader knows both *when* to replace sample data and *what* to replace the data with.

Avoid using foo , bar, acronyms, or gibberish terms that may mean a lot to your development team and not a lot to your reader. Terms like foo and bar may be familiar—even standard—to developers with a traditional background, but developers increasingly enter the field through nontraditional education and experience. It’s better to write looking forward than backward.

Use descriptive strings in a consistent style to describe replacement data. For example, use strings like your_password or replace_with_actual_bark (Listing 5-6).```shell# Provide code comments that tell users what to update or replace$ curl 'https://corgly.example.com/api/v1/translate' -i -X POST \  -H 'Content-Type: application/json' \  -d '{"query": "replace_with_actual_bark"}'```Listing 5-6Descriptive strings indicate where readers should replace code with their own data

Make sure it’s clear where you expect your reader to get any replacement data from. For example, in a sample where readers provide an access token, indicate where readers can find or create the access token.

### Trustworthy

Concise, clear, and usable samples ensure consistency, which builds trust with your reader. It only takes one incorrect or broken sample for your reader to lose trust in your documentation and by extension your software. For example, a sample error code that doesn’t match what readers actually encounter makes it much harder for users to diagnose and fix any problems.

Use production-ready code where possible so your readers can use your samples with confidence. Clearly mark any alpha or beta features to let readers know they may be subject to change.

To make sure your samples are trustworthy, test and review your code samples regularly. A later section in this chapter provides advice for testing. Chapter [11](505277_1_En_11_Chapter.xhtml) gives more guidance on overall documentation maintenance, including regular code sample reviews.

## Designing code samples

Designing your samples is as much about choosing what to include as well as presenting them to your reader.

### Choosing a language

Sometimes , it’s easy to get caught up in the question of which language to write your code samples in. If your users work primarily in one programming language, then answering this question is easy: provide samples in your users’ language.

If your users work in multiple languages, then you may find yourself struggling to decide which language(s), and how many, to support in your code samples. Generally speaking, provide samples in a single language that is familiar and most likely to be used by your readers. For example, choose the language of a popular client library supported for your API. For API documentation, consider providing curl samples and allowing your reader to generate samples in a language of their choice.

If you have the time and tooling, you can provide code samples in multiple languages, but be aware that adding multiple language samples adds additional maintenance overhead to your documentation.

### Highlighting a range of complexity

Every reader approaches your documentation with a different level of comfort and confidence in using your software. Your documentation should support readers across the spectrum of comfort and familiarity by providing code samples with a range of complexity. With a range of samples, your readers can opt to read and follow whichever layer of complexity is most helpful to them.

For complete newcomers, simple examples to help get started are usually most beneficial. Think of a typical “hello world” tutorial with small, short samples. Hello world exercises are quick to complete, don’t require much additional input from the reader, and provide lots of context to explain what is happening and why.

For readers more comfortable with your software, you may want to follow the newcomer-friendly options with more complex examples. These could be code samples for specific use cases when the reader is already familiar with the core concepts in your software. Limit examples to one use case per page: avoid mixing newcomer and advanced documentation!

### Presenting your code

Code samples need good presentation.

Since your code samples are what your readers are looking for, choose formatting and styles that help your code visually pop out of the page. You can use a surrounding box and a different font and background color to make your code samples visually distinct from the rest of your documentation.

The text of your code samples should also look like code. Limit sample lines to 80 characters, and format code samples in a fixed-width font. For example, use backticks in Markdown or the element in HTML.

Most documentation tools have predefined styles to help you format and present well-formed code samples. For example, some documentation platforms let you use tabs to present code samples in different languages.

## Tooling for code samples

As with all tooling advice, your mileage may vary. It’s up to you to decide what types of tools work best for your workflow, but code sample tooling falls roughly into three types:- Testing
- Sandboxes
- Autogeneration

NoteWe’ve deliberately avoided mentioning any specific tools for generating and handling code samples in this chapter because tools are constantly changing.

Before you dive into tooling recommendations, pause for a moment. As with all automation and tooling choices, the trick is knowing when to invest the time and energy to make the results worthwhile. Automation could be right for you—but automation alone doesn’t solve usability and maintenance problems. Before automating something, consider whether the time and energy you’d invest might produce more helpful results if placed instead into your writing, editing, information architecture, user research, or the product itself.

### Testing code samples

Code samples, especially runnable code samples your reader may use in production, must work. There are many packages available to help you test code samples before adding them to your documentation. You can also store the samples themselves in GitHub or another source repository and run tests against them there. Once the samples pass their tests, you can embed them in your documentation.

### Sandboxing code

Providing code in a sandbox lets you give your readers the chance to play with sample code safely. Unlike other types of code samples, a sandbox lets your reader interact with the sample before they implement it. Sandboxes help readers build greater trust with your software before using it in production.

Sandboxes take a lot of time and effort to create properly. A sandbox may be worth the investment if your software is particularly risky or sensitive in some way, and you’re sure you have the time and bandwidth to maintain it. Sandboxes are also incredibly helpful if your samples require a lot of customization to make them applicable to your reader.

In the majority of cases, sandboxes are likely excessive, and you may better meet your readers’ needs by investing in good test coverage for your samples or autogenerating them from source.

### Autogenerating samples

Autogenerating code samples directly from source can be incredibly helpful. Tightly coupling documentation and code often means easier maintenance and a better experience for both you and your reader.

For example, output code, like API responses or error codes generated with the help of an OpenAPI spec or similar tools, ideally mean that your code samples automatically reflect any changes to your API. However, no matter which tool you use, autogenerated samples need human input and review. Your readers need context to understand the intent behind your code. At minimum, human input often means rewriting code comments to make them reader friendly.

## Summary

Use code samples to accompany your explanations and vice versa.

Make sure your samples are:- **Explained**: Provide the why, not the what, behind your sample.
- **Concise**: Aim for minimal reproducible examples.
- **Clear**: Lean on existing conventions and style guides.
- **Extensible**: Make it clear where and how a reader needs to amend their own code.
- **Trustworthy**: Be consistent and test, test, and test again.

Tooling for code samples relies on testing, sandboxing, and autogeneration. Think before you automate!

Now that you’re well equipped to add code samples to your documentation, the next chapter covers adding visual content as well.

Footnotes1Tom Johnson, “Code Samples,” I’d Rather Be Writing, accessed June 26, 2021, [https://idratherbewriting.com/learnapidoc/docapis_codesamples_bestpractices.html](https://idratherbewriting.com/learnapidoc/docapis_codesamples_bestpractices.html).

2“Creating Great Sample Code.” Google Technical Writing One, accessed on June 15, 2021, [https://developers.google.com/tech-writing/two/sample-code](https://developers.google.com/tech-writing/two/sample-code).

3Jarod Reyes, “How Twilio writes documentation,” Signal 2016, YouTube, accessed June 26, 2021, [www.youtube.com/watch?v=hTMuAPaKMI4](https://www.youtube.com/watch%253Fv%253DhTMuAPaKMI4).

4We’ve used [example.com](http://example.com) as the Corg.ly domain in line with RFC 676, which permits the use of [example.com](http://example.com) for documentation, [https://tools.ietf.org/html/rfc6761](https://tools.ietf.org/html/rfc6761).

5Seyed Mehdi Nasehi, “What makes a good code sample? A study of programming Q&A in Stack Overflow,” *2013 IEEE International Conference on Software Maintenance*, 2012.
