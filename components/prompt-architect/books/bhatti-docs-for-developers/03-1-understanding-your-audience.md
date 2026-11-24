© The Author(s), under exclusive license to APress Media, LLC, part of Springer Nature 2021J. Bhatti et al.Docs for Developershttps://doi.org/10.1007/978-1-4842-7217-6_1
# 1. Understanding your audience

Jared Bhatti1, Zachary Sarah Corleissen2, Jen Lambourne3, David Nunez4 and Heidi Waterhouse5(1)Berkeley, CA, USA(2)Victoria, BC, Canada(3)Cornwall, UK(4)San Francisco, CA, USA(5)Mounds View, MN, USA
## Corg.ly: One month to launch

*Charlotte was frustrated. The launch date for Corg.ly was just a few weeks away, yet it took the entire engineering team (well, all five engineers) an afternoon to get a single user started.*

![../images/505277_1_En_1_Chapter/505277_1_En_1_Figa_HTML.jpg](/api/v2/epubs/urn:orm:book:9781484272176/files/images/505277_1_En_1_Chapter/505277_1_En_1_Figa_HTML.jpg)

*Mei, their alpha customer, was extraordinarily patient as Charlotte demonstrated how Corg.ly worked and how to use the API. Charlotte had spent the previous hour sketching out a system diagram, some of the design decisions made, and how endpoints sent and received data. Ein, the company dog and official product tester, had happily demonstrated how bark translations worked in exchange for a few dog biscuits.*

*Reflecting on the time spent in this meeting, Charlotte realized these sessions were time consuming and costly. If the product was going to scale to the large audience they projected, users were going to have to get started by themselves, and quickly.*

*As if reading Charlotte’s mind, Mei leaned back in her chair. “I still have a lot of problems getting this working, and I know I’ll have a million more questions once I do. Can you send me the docs when they’re ready, and I’ll happily give it another try?”*

*“Of course,” Charlotte said. She felt a pit open in her stomach as a montage of vignettes from the past six months flashed through her mind: multiple instances where she had said things like, “Let’s wait on the documentation, since everything is just going to change anyway... Let’s deprioritize the documentation for now, since there’s so much else to do... We probably don’t need to worry about documentation right now since the code is self-explanatory...”*

*“Thanks,” said Mei. “I’m excited to share this with the rest of my team, but I know you’re the experts. It’s going to take time to teach the developers on my team how to develop against your API, but we need to start soon. We’re hoping to produce several million dog translator collars for Christmas this year.”*

*“Sure thing. We’ll polish up the docs and share them when they’re ready. We should have drafts ready in the next few weeks,” responded Charlotte.*

*As the lead engineer, she architected the product and worked closely with her coworker, Karthik, to dole out the tasks and assignments to everyone, none of which included documentation. Corg.ly was in fact heavily documented—in a mishmash of emails, scattered meeting notes, and pictures of whiteboards. As the architect of the product, she had an intimate knowledge of the code, what it could do, and the trade-offs they made along the way.*

Corg.ly is so easy for me to use, I didn’t think about how hard it might be for others, *Charlotte thought to herself after the meeting.* Where do I start?

## The curse of knowledge

In the late 1980s, a group of economists at Harvard determined that humans assume others have the same knowledge they do. They named this cognitive bias the “curse of knowledge.”[1](#Fn1) A few years later, a Stanford PhD student demonstrated the curse in an experiment. She asked one group of participants to tap their fingers to the rhythm of a well-known song while another group of participants listened to the taps and tried to guess the tunes. The tappers, with the song fresh in their mind, assumed their listeners would be able to guess the majority of songs.

Listeners didn’t.[2](#Fn2) Tappers guessed that listeners would predict the song 51% of the time, but the unfortunate listeners only got the song right a mere 2.5% of the time.

It’s likely you’ve been on the receiving end of the curse of knowledge. A coworker may have used jargon you weren’t familiar with, forgot to mention an API endpoint they assumed you would find, or pointed you to an error message with very little information on how to fix the problem. For Corg.ly, Charlotte has spent so much time with the product that she knows it perfectly, but the first few users trying out the product have no idea how to make sense of it.

Breaking the curse, and writing effective documentation, requires empathy for your users. You have to understand what your users want from your software, and where they need help along the way. Through user research, you can understand your users’ needs well enough to predict what they need before they need it. By performing user research before you put pen to paper or hands to keyboard, you’ll set your users on the path to success.

This chapter guides you through breaking the curse of knowledge and understanding your users by:- Identifying the goals you have for your users
- Understanding who your users are
- Understanding your users’ needs and how documentation addresses them
- Condensing your findings into personas, stories, and maps
- Testing your assumptions with a friction log

## Creating an initial sketch of your users

To write effectively for users, you need to understand who they are and what they want to achieve.

Start by gathering and reviewing any existing materials you already have about your product or your users. These could include old emails, design documents, chat conversations, code comments, and commit messages. Reviewing these artifacts will help you build a clearer picture of how your software works and what you intend your users to do with it.

Users also have their own goals that may or may not match those of your organization. An initial review can help identify any initial gaps or mismatches between these different sets of goals.

### Defining your users’ goals

Once you review your existing knowledge, the next step is to understand what your users want to accomplish from reading your documentation. Knowing your users’ goals will guide your research and focus your efforts on documenting the most relevant information.

Consider: why are you writing this documentation in the first place? You don’t just want your users to know something about your software; you want them to complete a set of tasks or change their behavior in some way. There is an engineering goal (for them) and a business goal (for you) that you want your users to reach.

At Corg.ly, Charlotte needs to onboard as many new users to Corg.ly as possible for the business to be a success. The goal of Corg.ly documentation can be summarized as> *Onboard new users to Corg.ly by helping them integrate with Corg.ly’s API.*

By contrast, the most common goal of Corg.ly users is> Translate my dog’s barks into human speech.

The goals of Corg.ly and Corg.ly users are different, but they can still align in a single documentation set. You probably have a goal for your users as well. Identifying how different goals can both differ and overlap helps you gain empathy and meet needs effectively.

The following sections in this chapter will help you break your goal down into smaller goals as you research your users and their needs. However, it’s important to define your overarching user goal from a business standpoint first.

NoteOnce you determine your goal for users of your product, write it down. Later, you can measure the success of your documentation by how well it meets your goal. (For more information about measuring documentation success, see Chapter [9](505277_1_En_9_Chapter.xhtml).)

### Understanding who your users are

Now that you know what you want your users to achieve, you can identify who they are. You can define them in a variety of ways. For example, you can define users by their role, such as developers, product managers, or system administrators.

Alternatively, you can define users by their level of experience or by what situation they’re in when reading your documentation. For example, are they junior developers new to their roles? Will they be using your documentation at 4 a.m. after waking up to a pager alert?

Remember your curse of knowledge. The knowledge, skills, and tools you have may be very different from your users.

NoteNot every user is the same, and you can’t meet every user’s needs. Prioritize the users who are most important for your product or business.

For example, if your software will primarily be used by developers, then focus on understanding *developers’* needs—as opposed to those of a product manager who may be evaluating your software for an engineering team. Consider what kind of developer your user is: an application developer using an API needs different things than a site reliability engineer (SRE) focused on security and reliability.

As you think through these questions, write down a list of characteristics that your users share. Keep it focused and brief. For a developer audience, consider characteristics like:- Developer skill
- Programming languages
- Developer environment
- Operating system
- Team role

A list of characteristics gives you a starting point for user research. You can add more categories later as your research progresses.

### Outline your users’ needs

Once you create a basic definition of who your users are and the overall goal you want them to accomplish, you can start outlining what your users need. The easiest approach is to list questions your users will have about your product that your documentation will need to answer.

Some questions, in general, apply to all products. Questions like:- What is this product?
- Will this product solve my problem?
- What features are available?
- How much does it cost?
- How do I get started?

Other questions are going to be very specific to your product, your users, and their goal:- How do I authenticate against your API?
- How do I use a specific feature?
- How do I troubleshoot a specific problem?

You’ll identify some of these questions immediately through your experience with your own product, but remember your curse of knowledge. Your users don’t know as much about your product as you do, so they will likely have basic questions about your product that you’ll need to answer. As you do more research into your users and validate your understanding, you can add additional questions for which users need answers from your documentation.

## Validate your user understanding

Once you have a definition of your users, their goals, and their needs, you should validate and build on your initial understanding. User research helps you confirm who your users are and what they need from your documentation.

The quickest way to confirm or reject your assumptions about who your users are and what they need from your documentation is to talk to them directly. Interacting directly with users is a surefire way to help you understand what they’re trying to do with your software, how they’re currently using it, and any frustrations or concerns they have.

NoteThe focus here is on your users’ *needs*, which are different from user *wants*. Consider asking someone how they want to travel to a nearby town. Given all the options in the world, they may say they want to drive there in a sports car. This is a good representation of their desires. Who wouldn’t want to travel by sports car, given the option? But if that same person doesn’t know how to drive, a better option may be to offer them a bus ticket. They *want* the sports car, but they *need* a bus ticket. When researching, work on identifying these needs, even when they are buried in a pile of wants.

### Using existing data sources

The easiest way to connect with your users is to find the places where communication channels already exist. If you’re part of a larger organization, you might have access to teams who are already having conversations with users whom you can reach out to. These teams include:- Developer relations
- Product support
- User experience
- Marketing

These teams can help you validate your assumptions about your user and give you additional information, for example: What do we already know about our users’ experience with the software? What are their blockers or pain points? How long does it take for a user to complete a successful integration?

#### Support tickets

Support tickets  are an existing data source and a gold mine for understanding your users. Nothing beats the content of a support request sent in the heat of the moment by a frustrated user for understanding what your users need most. In addition, you can follow up with the user who filed the support ticket and see if they would be willing to speak with you directly.

To analyze your support issues, pull a list of recently filed issues that relate to what you’re documenting, and then group them by theme (Table 1-1).Table 1-1Grouping issues with examples

| Issue | Example |
| --- | --- |
| Topic | *Users are confused by the name of a particular endpoint* |
| Process | *80% of users had issues authenticating* |
| Type of user | *Developers who recently started using Corg.ly are more likely to request help* |
| Action | *We helped 4/5 users by rewriting a particular error message to give more information* |

Some themes may be immediately obvious. Others can take some time to appear. Get a colleague to join you to see if they can spot themes you didn’t notice. Remember the curse of knowledge is always at play; anything or anyone you can involve to challenge your own biases and knowledge is useful at this stage.

As patterns emerge, add your discoveries to your initial definition of the user. Is the experience level of users filing support issues higher or lower than you expected? Are they using specific tools or languages that you should consider documenting? Did they express  common needs that many users likely share?

### Collecting new data

Sometimes, existing data sources aren’t available or aren’t enough to validate or refute the assumptions we have about our readers. This is a perfect opportunity for more in-depth research collection methods. However, it’s important to note that good research can be time consuming. Although the return on your time investment will be huge, it can be tricky to find the balance between the right amount of research and the need to get your documentation in front of your readers quickly.

However scrappy your research, something is usually better than nothing. You can scale the following research methods as you feel is appropriate to break your curse of knowledge.

In some cases, approaching existing online communities for their views or speaking with attendees at a developer conference may be sufficient for you to break the curse and validate your assumptions. In other cases, you may need to invest more time in in-depth interviews and surveys.

NoteWhatever method you choose for your research, if you are collecting user data, you need to keep your participants and their data safe. You must consider how you get consent from your participant and keep their information secure.[3](#Fn3)

In addition, familiarize yourself with local data protection laws if you choose to collect any personal data. For example, in the EU and UK, the General Data Protection Regulations (GDPR) outline how organizations must handle any collection of personal data.

#### Direct interviews

Where themes overlap or requests seem the most pressing, interviews can help you dig a little deeper. Provided you are considerate of their time, most people like the chance to help shape a future product or documentation .

Consider what existing routes you can use to find participants for interviews. Are there online communities where users of your software typically chat with each other? Are there upcoming conferences or other events where you could meet potential users? Do you have a few early adopters who would be interested in talking to you?

Regardless of your interview source, pursue quality over quantity. Five potential readers who fit your target audience will offer much more valuable insight than fifty people who didn’t meet your criteria, but were easier to find—and if you can only find five participants, that’s okay, too. Advice varies, but around three to five people for one “round” of research is considered a robust enough sample  on which to base future content decisions.[4](#Fn4)

NoteConsider the diversity of the people you talk to. Look at the age, gender, disabilities, ethnicity, job duties, and social and economic status of your pool. Are your interview participants representative of the wider group of people who will eventually read your documentation?

When performing the interviews, it’s important to prepare your topics in advance to keep the conversations focused and useful. Some high-level topics for the Corg.ly API could be:- Previous experience using similar services and APIs
- Expectations while using the Corg.ly API

Break each topic down into specific, open questions. A specific question bounds the scope of possible answers in a helpful way. An open question is exploratory, usually answered with a story or longer explanation. By contrast, a closed question is limited and usually answered with a yes or a no. For example, “Have you used pet translation software before?” is a closed question. You can rephrase it as an open question by asking, “What’s your experience using translation software?”

If possible, ask the interviewee to walk through the steps of doing the task that you’re documenting. Observe them and see where  they get stuck, and have them talk through their process and frustrations.

At the end of your interviews, you should have recordings or transcripts of each session and high-level observations. While interviews are handy for asking open questions, sometimes you may need more directly comparable data to understand what your readers need. This is where surveys can be a handy part of your research repertoire.

#### Developer surveys

If you have a large group of people from whom you’d like to gather information, a well-designed survey can give you more actionable and immediate insights, especially if you don’t have much time for in-depth interviews. The trick to great surveys is to make them quick and painless.[5](#Fn5)

To make a survey quick and painless, you need to create a small set of targeted questions. As with planning interviews, you’ll need to know what you want to find out—and asking fewer questions is more impactful than trying to cover everything.

Good survey questions:- Ask one thing per question
- Are closed (with limited answers)
- Optional to answer
- Are neutral

Even the most perfectly designed questions are only useful if people answer them. There are several tactics you can use to increase your response rate. Make it clear who you are, what data you’re collecting, and why. Write your questions carefully so they are easy to answer. If you demand too much from your responder, it’s likely they will not complete the survey or annoy them so much it skews their responses.[6](#Fn6)

Finally, you can consider incentives or rewards for taking part in your research. This could be a monetary reward or a voucher, but you could also offer access or information, for example, beta access to the Corg.ly app, or their name included in a public list of contributors.

## Condensing user research findings

Compiling your results and observations from research can feel unnecessary. You’ve probably gathered a lot of information about problems you want to immediately fix, but hold up! That rush of knowledge is easily lost, and it’s worth taking the time to condense your findings into tangible records you can refer to during later stages of writing documentation.

Three useful ways of condensing your user research findings are:- User personas
- User stories
- User journey maps

### User personas

A *user persona* is a semi-fictional character created to represent your ideal reader or readers. This character can be based on a specific person or an amalgam of people you learned about in your research. A user persona usually includes a short description of the individual (real or imagined) and a list of their goals, skills, knowledge, and situation.

To build a user persona, compile a list of the essential characteristics you’ve learned about your users through your research. For example, here’s a user persona for an advanced developer based on Mei, Corg.ly’s alpha customer:
|  |  |
| --- | --- |
| **Name:** Mei |  |
| **Developer skill** | Advanced |
| **Languages** | Python, Java |
| **Developer environment** | MacOS, Linux |
| **Role** | Lead developer |

There are also a number of junior developers using Corg.ly. Here’s a persona named “Charles” that represents them:
|  |  |
| --- | --- |
| **Name:** Charles |  |
| **Developer skill** | Beginner-Intermediate |
| **Languages** | Python |
| **Developer environment** | MacOS, Linux |
| **Role** | Junior developer |

Once you create your personas, consider which persona you want to focus the rest of your research on. In the example of Charles and Mei, it’s probably most useful to focus on people similar to Charles when creating documentation. There are many more developers like Charles who need more guidance and explanation than there are advanced developers like Mei who will understand your product quicker.

As you develop your own user personas, consider the needs of your users. Who do you need to help most? Who would face the biggest learning curve to use your software? Who is most important for the adoption of your product?

### User stories

If you have more time, you may find it useful to write *user stories* alongside your personas. User stories are short written summaries of what a user is trying to achieve and are a nifty way to condense your users’ needs to keep them front of mind for the planning, writing, editing, publishing, and maintenance that comes next. You may be familiar with the idea of user stories from working in Agile product teams.

> *A*user story   *tends to follow the same format:**As a [type of user], I want [activity] so that I can [goal]*.

You can break down your research findings into many of these kinds of statements. You can also take one significant part of your research and create multiple user stories for it. An example user story for a Corg.ly user could be:> *As a developer, I want to integrate Corg.ly data with my smart watch so I know what my dog is saying when we’re out for a walk.*

The user story is not focused on knowing how to use the API or wanting great documentation. It’s focused on the higher-level tasks users are trying to achieve and their motivations for it.

### User journey maps

For meatier research projects with ample research notes and text, a visual illustration can be handy. A *user journey map*   is a diagram showing the path a user takes through a product or website while trying to accomplish a particular task. The map usually covers all routes or “channels” a user may take when interacting with your software and documentation. The map is a timeline, tracking what a user does at each point in their journey and what they feel or experience at each step. Creating a user journey map can be a succinct way to condense your findings, highlighting where your users are happiest, and where you can improve.

To create a user journey map:1. 1.Define the task the user is trying to accomplish.
2. 2.List the channels a user may interact with (e.g., your website, docs, your code repository, or the app itself).
3. 3.Piece together the steps a user takes through each channel (e.g., discover, sign up, install, configure, test, run, review).
4. 4.List the user experience at each step (e.g., what they are doing, feeling, thinking).
5. 5.Connect the channels, steps, and experiences in a flow.

Figure 1-1 shows an example map of a user journey where a user evaluates, signs up for, and connects to Corg.ly. The top row shows common user questions identified through Charlotte’s research. The middle row shows the user’s experience throughout the journey (where the current experience is meeting or not meeting their needs). The final row lists opportunities for Charlotte’s team to add or improve the documentation or product to provide a better experience.![../images/505277_1_En_1_Chapter/505277_1_En_1_Fig1_HTML.jpg](/api/v2/epubs/urn:orm:book:9781484272176/files/images/505277_1_En_1_Chapter/505277_1_En_1_Fig1_HTML.jpg)

*Figure 1-1User journey map for connecting to Corg.ly*

It may take several iterations to find a design that works for you. You may find it useful to emphasize where your users are not having a good experience or where there are few channels to help them through difficult steps.

## Creating a friction log

Equipped with your research findings, you now know the context, knowledge, and skills of your user. You know what they’re trying to achieve and why. Now it’s time to step into the shoes of your reader and experience for yourself the friction that stands in their way.

Friction can manifest in different ways. Frustration, anger, disappointment, and stress are all symptoms of friction that result in the same thing: distrust and disengagement with your software.

A *friction log*  is a journal in which you try your software as a user would and record your experiences. To record your experience, log each step sequentially, noting the behavior you expect and the actual behavior of your software. The bigger the gap between expectation and reality, the bigger the opportunity to improve your docs or software.

The best friction logs have a tight scope to prevent sprawl and keep results actionable. Pick a user and a scenario with a clear beginning and end, for example, a developer installing your software for the first time. Note the scenario and any other test information at the top of the page, such as the environment or version you’re using.

Now it’s time to work through the steps and record the experience. As best you can, let go of your existing knowledge and your own mental models. Put yourself firmly in that user’s shoes: How does it feel to complete a step? Did it seem easy? Are you reassured you’re on the right track? Are you feeling unsure? Lost? Annoyed?

Format your friction log into numbered steps, breaking down each task into its own line. For example, to start using the Corg.ly API, the first step is to sign up for a paid Corg.ly account. The process of completing that task contains a lot of friction, outlined in the following friction log:
| **Goal:** Start using Corg.ly API |  |
| --- | --- |
| Tasks | Friction log |
| 1. Sign up for a paid Corg.ly account. | 1. Opened Corg.ly website.    2. Navigated to web form for sign-up. Had to scroll to the bottom of the page. Difficult to find. Maybe add to top of page?    3. Completed form. Put in credit card information.    4. Clicked submit button. Did not receive confirmation it had been submitted. No error generated.    5. Noticed some form fields were blank. Did the empty fields stop the form from submitting?    6. Filled in blank fields.    7. Clicked submit button. Received confirmation message and reassuring information has been sent.... |

You may find it useful to color code your friction log to indicate positive and negative user experiences. For example, green could indicate steps that were easy to complete, offered clear evidence of success, and guided you to the next step, or red for steps that were particularly frustrating or stopped you from progressing.

At the end of the scenario, examine your log. Are there any steps that were particularly difficult, or areas that were manageable but could be improved? Friction logs offer a chance to reflect on what steps could be improved by documentation and which by software changes. You may have identified issues that are fixable in the product (a missing error message, a typo in a command) rather than documentation. Consider creating a bug report or issue to capture these and free your time to focus on writing documentation for where it matters most.

You don’t need to restrict friction logging to the early stages of your documentation project. Rerunning or picking a new area to log is a great way to reconnect with your readers and remember what it feels like to experience your software as a newcomer, as well as find new improvements to make. In time, you can test the usability of your documentation itself alongside your software, which can be a handy means of measuring the effectiveness of your documentation. For more information on measuring the quality of your documentation, see Chapter [9](505277_1_En_9_Chapter.xhtml).

## Summary

Effective documentation requires you to have empathy for your users, which you can build with user research and its tools: interviews, developer surveys, and reviewing support issues. Condense your research into user personas, user stories, and user journey maps that you can refer to later.

Empathize with your users by trying out your own software and documenting your experience in a friction log. Notice the places in your product where you can help your users through documentation or through product improvements.

The next chapter covers how to turn your empathy into action by creating a documentation plan.

Footnotes1Colin Camerer, George Loewenstein, Martin Weber, “The Curse of Knowledge in Economic Settings: An Experimental Analysis,” *Journal of Political Economy,* Vol. 97 no. 5.

2Elizabeth Louise Newton Ph.D., “*The Rocky Road From Actions to Intentions*,” Stanford University, 1990, 33–46.

3Maria Rosala, “Ethical maturity in user research,” Nielsen Norman Group, published December 29, 2019, [www.nngroup.com/articles/user-research-ethics/](https://nngroup.com/articles/user-research-ethics/).

4Jakob Nielsen, “Why you only need to test with 5 users,” Nielsen Norman Group, published March 18, 2000, [www.nngroup.com/articles/why-you-only-need-to-test-with-5-users/](http://www.nngroup.com/articles/why-you-only-need-to-test-with-5-users/).

5Jakob Nielsen, “Keep online surveys short,” Nielsen Norman Group, published February 1, 2004, [www.nngroup.com/articles/keep-online-surveys-short/](http://www.nngroup.com/articles/keep-online-surveys-short/).

6Gerry Gaffney and Caroline Jarrett, *Forms that work: Designing web forms for usability* (Oxford: Morgan Kaufmann, 2008), 11–29.
