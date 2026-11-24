© The Author(s), under exclusive license to APress Media, LLC, part of Springer Nature 2021J. Bhatti et al.Docs for Developershttps://doi.org/10.1007/978-1-4842-7217-6_8
# 8. Gathering and integrating feedback

Jared Bhatti1, Zachary Sarah Corleissen2, Jen Lambourne3, David Nunez4 and Heidi Waterhouse5(1)Berkeley, CA, USA(2)Victoria, BC, Canada(3)Cornwall, UK(4)San Francisco, CA, USA(5)Mounds View, MN, USA
## Corg.ly: Initial feedback

*It had been two weeks since Charlotte’s team published Corg.ly’s first set of documentation on their website. After taking a short break to celebrate and relax, Charlotte and Karthik wanted to know how readers are responding. Was the documentation as helpful as they’d hoped?*

*Karthik emailed Mei to see if her team had any feedback and included a short questionnaire for the group. After he received the questionnaire results, Karthik asked Mei for a follow-up meeting.*

*“Thanks for meeting with me,” Mei started, “and asking for feedback from me and my team. Overall, the documentation is good, but we have some questions. The docs don’t seem to cover formatting parameters for the length of a bark...”*

*Karthik took notes as Mei outlined other issues that her team was facing. Some of the issues were product issues, and some were issues with documentation. He started thinking about ways to organize these issues when Mei surprised him with a question.*

![../images/505277_1_En_8_Chapter/505277_1_En_8_Figa_HTML.jpg](/api/v2/epubs/urn:orm:book:9781484272176/files/images/505277_1_En_8_Chapter/505277_1_En_8_Figa_HTML.jpg)

*“Is there a better way for us to get you feedback?” Mei asked. “I appreciate you taking time with me, but I know this kind of interaction won’t scale for all your users.”*

*Mei was right—fixing her team’s issues would be fairly easy, but getting feedback one to one like this wouldn’t scale to all of Karthik and Charlotte’s users. Also, what if Mei’s team was an outlier in the kind of feedback they got? Karthik knew he needed to think more about this and chat through some ideas with Charlotte.*

## Listening to your users

Documentation is one of the primary ways you communicate with your users, and users expect to be able to communicate back. Collecting user feedback can help you learn where your product and documentation succeed and where you need to make improvements. It also helps you validate (or correct) all the assumptions you’ve made about your users in your initial user assessment (see Chapter [1](505277_1_En_1_Chapter.xhtml)).

At first glance, gathering and understanding all the feedback your users have may feel overwhelming. You put a lot of effort into your code and your documentation, and user feedback can feel judgmental, confusing, or just plain unhelpful. It’s a daunting task to sort useful, constructive feedback from feedback that’s not.

That said, documentation plays a critical role in addressing users’ needs and helping them understand your product and be productive. User feedback provides critical information on how your documentation and product perform, and your users often provide suggestions that you can use to improve both your content and your code.

This chapter guides you through the process of gathering user feedback and making it actionable by helping you:- Create user feedback channels
- Convert feedback into action
- Triage the feedback you’ve received from users

NoteFeedback and metrics are closely related. For more information on metrics, see Chapter [9](505277_1_En_9_Chapter.xhtml).

## Creating feedback channels

If you have a small number of users, you might communicate with them individually through email and chat, or through small meetings like the one Karthik is having with Mei. As your users increase in number, these ad hoc methods of getting feedback don’t scale. Users will still try to reach you—through mountains of emails, Twitter posts, and Stack Overflow questions—and you’ll find yourself in the painful place of playing “whack-a-mole” trying to keep up with all of the messages you’re getting.

The solution is to create channels for user feedback that you can use to improve your documentation and code. *Feedback channels*  are specific means or venues for your users to connect with you. Feedback channels include everything from allowing users to submit issues directly against your documentation to requesting feedback through customer surveys.

There are many creative ways to gather feedback from your users. For the purposes of this chapter, we focus on these channels that relate closely to documentation:- Accepting feedback directly through documentation pages
- Monitoring support issues
- Collecting document sentiment
- Creating user surveys
- Creating a user council

Each of these channels provides a different kind of feedback from your users. For example, accepting issues filed by users directly through your documentation pages provides you with feedback on individual pages, whereas contacting customers periodically can give you higher-level feedback about both your documentation and product.

This list of channels isn’t exhaustive, nor should you try to implement every channel. Listening to your users means respecting their time, so carefully consider which channels are most useful for you and least time consuming or distracting for your readers. After all, your readers came to your documentation to understand your product, not to submit feedback.

### Accept feedback directly through documentation pages

Accepting feedback directly through your published pages gives readers a way to contact you if they have a specific issue with the page. For example, a user might find one of the steps in your process confusing, or a code sample that you’ve published doesn’t work.

For small projects, you can add a short script to a page that displays an email link and appends the page title and URL to any email sent. Alternatively, you can provide a link that sends feedback to the same system you use to manage bugs and issues for code. This is particularly useful for larger projects where users submit a lot of feedback: it’s easier to track, measure, and respond to feedback if you track it in the same place as your code issues.

Most issue tracking systems allow you to collect information through a form or template. This is particularly useful when collecting feedback from your users. An issue template gives your users additional structure for their feedback, guiding them away from sending unhelpful or cryptic feedback about your documentation. The following example is an issue template for Corg.ly docs. This example assumes that Corg.ly documentation uses a Markdown-based issue template:## Title<!--- Provide a short summary of the issue-->## Document URL<!-- Copy and paste the relevant URL(s) into this section. -->## What's wrong or missing?<!-- Clearly explain the specific impact. Attach screenshots if necessary. -->## Possible solution<!-- Not required. Describe how the document can be more helpful. -->The goal of page-level feedback mechanisms is to give users an opportunity to respond directly from the content. They give you the most granular feedback on where to improve the documentation.

### Monitor support issues

If your organization has a support team, they’re a good partner for collecting and understanding user feedback. Your support team likely has feedback channels of their own that customers use to get help, and they probably have an incident management system for logging customer issues, documenting workarounds, and generating reports.

If possible, work closely with your support team to understand commonly reported issues and trends of customer feedback. If customers experience the same issue over and over, it needs to be addressed through either documentation or a product update.

### Collect document sentiment

Document sentiment is how readers feel about your documentation. You can discover and measure document sentiment through a simple survey or by using embedded code on a page that prompts a user to indicate by clicking a simple yes or no whether the page was helpful (Figure 8-1).![../images/505277_1_En_8_Chapter/505277_1_En_8_Fig1_HTML.jpg](/api/v2/epubs/urn:orm:book:9781484272176/files/images/505277_1_En_8_Chapter/505277_1_En_8_Fig1_HTML.jpg)

*Figure 8-1A document sentiment tool on a Google page*

If your pages have low ratings, you can improve the pages, then measure the effect of those changes on sentiment. If your pages get high ratings and you know why, you can replicate that success elsewhere.[1](#Fn1)

There are significant limitations to measuring sentiment. You need to collect a large number of responses from a yes/no sentiment survey in order for data to be useful. The more responses you get, the more confident you can be that the data actually represents your users. You also have to wait after making changes before collecting more responses to measure whether changes had an effect.

Sentiment can also be highly contextual. For example, a troubleshooting  page might have low sentiment because readers of that page arrive there frustrated. Even if the page is helpful, users might rank it low. You can get more context about why users feel the way they do about your pages through follow-up questions or surveys.

### Create user surveys

Customer surveys  let you ask users specific questions about your product and documentation in an automated way that’s easy to aggregate. You can embed shorter surveys in your documentation, either as a link or as a popup. Longer surveys can be emailed to your customers.

Regardless of how you reach your users with a survey, it’s important to keep your survey focused on a specific set of questions with measurable results. For example, if Karthik wanted to understand user satisfaction with Corg.ly’s documentation, he might create a survey that asked the following questions:1. 1.How satisfied are you with Corg.ly’s documentation?
2. 2.Are you able to find the information you were looking for?
3. 3.How much time did it take you to find this information?
4. 4.Did this effort match your expectations?
5. 5.What can we do to improve our documentation?

A survey like this helps generate a *customer satisfaction score* , also known as CSAT. Once you have enough responses to establish a baseline, you can track changes in CSAT as you publish more documentation or address issues that users raise against your current documentation.

NoteCreating a good customer survey requires specific knowledge and skills. There are many guides and tools to help you create helpful surveys that yield insightful results. Doing research before publishing a survey makes a significant difference in the quality of results and helps you avoid annoying your users with an intrusive experience.

### Create a user council

If you have a small number of critical users for your product, you can establish a user council to get their feedback. A user council is a group of current or potential users who are willing to give you advice on your product.[2](#Fn2) Typically, it’s because they’re early adopters and want you to succeed or they are current customers who expect to make a big investment in your product or service. Mei, from this book’s Corg.ly stories, is a good example of someone who would be a perfect fit on a user council.

User councils can provide feedback on your documentation and your product as members try out new services. They can also help answer questions through one-to-one interviews, usability testing, and surveys. Having a user council means that you always have a dedicated group of people on hand if you need input or feedback on a new feature or document. It also helps you build a relationship with a core group of users who can evangelize your product to others.

## Converting feedback into action

When you gather data from the various feedback channels you create, you’re amassing information on the changes your users want. Some feedback will be concrete and easily actionable, like, “This particular code sample in this particular document needs an update.” Other feedback will be more complicated or require you to consider whether you need to improve your code or revise your information architecture.

You need a process to convert user feedback into action, one that allows you to prioritize issues that are most important to your users, and backlog the issues you can ignore or defer to another time.

The name for this process—of sorting and prioritizing feedback—is *triage*. Not all opinions deserve consideration, and not every great idea deserves immediate action. Triage helps you choose the most valuable improvements to make with limited resources.

### Triaging feedback

As in healthcare settings that evaluate patients upon arrival to make sure each patient receives an appropriate level of care, user feedback requires similar triage. Each feedback issue should be quickly evaluated to see if you can answer the following questions:1. 1.Is the issue valid?
2. 2.Can it be fixed?
3. 3.How important is the issue?

The following sections dive into each of these questions, defining specific requirements for answers at each step. Answering these questions helps you separate actionable user feedback from feedback that needs more information and feedback that can be ignored. Applying a standard triage process is critical because it:3- Speeds up the response times to user issues
- Prevents requested work from lingering endlessly
- Builds a standard set of priorities for issues
- Directs limited resources toward the most necessary and impactful changes

Triaging feedback for documentation is no different from triaging code or product issues. If you already have a system for managing issues, you should apply that system to managing your user feedback as well.

#### Step one: Is the issue valid?

It’s important to take a “trust but verify” approach when evaluating user feedback issues. Users have good intentions when submitting feedback, but sometimes their feedback isn’t relevant to documentation, or the issue they’re describing has already been fixed.

The first step to triaging user feedback is to determine whether it’s *valid*. In this case, validity means the issue is relevant to documentation.

Even if you build feedback channels specific to documentation, you will likely still get feedback on unrelated issues. Common examples include product feedback (a feature didn’t behave as expected, or a desired feature is missing) and requests for support (a reader struggles to complete a certain task in their local environment). These may be valid issues, but they’re not issues with the docs, so effective triage means routing unrelated issues to more appropriate teams.

#### Step two: Can the issue be fixed?

Once you’ve determined that the feedback is applicable to documentation, the next step is to determine whether the feedback is *actionable—*that is, whether you can act to change the documentation for the better.

For a documentation issue to be actionable, it must be:- Original
- Reproducible
- Scoped

For an issue to be original, it can’t be a duplicate of an issue submitted by other users. Having a searchable issue tracking system makes searching for duplicates much easier. If an issue has many duplicates, note the existence of duplicates in the original issue and close all the duplicates. You should also consider increasing the original issue’s priority if multiple users are reporting the same issue.

Next, try to reproduce the issue. Users might have an issue they think is the fault of your code or documentation, but it could be an issue in their local environment. If you can’t reproduce the issue, you can respond to the feedback with a request for more information to help you better understand the problem. Asking for additional details about their environment and the specific code they’re using can help you diagnose the issue.

Finally, scope the issue to something that’s possible to fix. Feedback that’s too general in scope (e.g., “These docs didn’t help”) isn’t feedback on which you can act. The same is true for feedback that’s too large in scope (e.g., “Rewrite the entire security section”).

Narrow the scope of an issue to something you can fix. For example, “The setup section for audio translation is difficult to follow and should be rewritten.” Limit the scope of each issue to a specific documentation fix that directly improves the user experience. Break down any required changes into smaller steps until you’ve created a well-bounded set of actions to take.

#### Step three: How important is the issue?

The last step of triage is to assign a priority to the issue. An issue’s priority encapsulates how important the issue is and how quickly it needs to be fixed.

Most projects have a standard set of priorities for issues. For example, Table 8-1 lists a set of issue priorities for the Chromium project.4Table 8-1Issue priorities

| Priority | What it means |
| --- | --- |
| **P0** | Emergency: requires immediate resolution |
| **P1** | Needed for upcoming release |
| **P2** | Wanted for upcoming release (but not required) |
| **P3** | Not time sensitive |

These priorities are identical across the Chromium organization. They’re easy to understand, and they can be quickly applied to any incoming issue. This prioritization scheme makes it easy to see at a glance which documentation issues to address quickly and which issues to defer until later.

### Following up with users

As stated at the beginning of the chapter, feedback is how you have a conversation with your users. It’s important to communicate with users about how you’re taking action on the issues they raised.

For example, if a user reports an issue that you can’t reproduce, the quickest way to address the issue is to ask for more specifics, including any code the user can provide you to help diagnose the issue and any information about their specific environment that might not be covered by your documentation. Asking users for more information about their feedback is quicker than trying to figure out the reported issue on your own.

It’s also important to follow up with users when you fix the issue they reported. Some issue trackers let you follow up with the user who submitted the issue. Otherwise, you can reach out to them directly and thank them for their feedback. If a user goes above and beyond in their feedback, you can praise them in release notes or blog posts after you fix the issue.

Let your users know that you’ve listened to their feedback. It takes time for users to submit feedback, so it builds trust when you let your users know they’ve been heard.

## Summary

Documentation is one of the primary ways you communicate with your users, and users expect to be able to communicate back through user feedback.

There are many feedback channels you can build to collect user feedback related to documentation, including:- Accepting feedback directly through documentation pages
- Monitoring support issues
- Collecting document sentiment
- Creating customer surveys
- Contacting customers periodically
- Creating a user council

After you collect feedback, triage issues with a process that validates and prioritizes each issue. Follow up with users when you fix the issues they report.

The next chapter covers how feedback is closely related to measuring documentation quality and gives you tools to measure where and how your documentation succeeds.

Footnotes1“Widgets,” Pete LePage, Google Web Fundamentals, accessed January 28, 2021, [https://developers.google.com/web/resources/widgets](https://developers.google.com/web/resources/widgets).

2“What we learnt from building a User Council,” Charlie Whicher, [Medium.​com](http://medium.com), published Nov 13, 2017, [https://medium.com/@CWhicher/what-we-learnt-from-building-a-user-council-541319c5c356](https://medium.com/%2540CWhicher/what-we-learnt-from-building-a-user-council-541319c5c356).

3“Issue Triage Guidelines,” Kubernetes, 2021, accessed June 27, 2021, [www.kubernetes.dev/docs/guide/issue-triage/](http://www.kubernetes.dev/docs/guide/issue-triage/).

4“Triage Best Practices,” The Chromium Projects, accessed May 14, 2021, [www.chromium.org/for-testers/bug-reporting-guidelines/triage-best-practices](http://www.chromium.org/for-testers/bug-reporting-guidelines/triage-best-practices).
