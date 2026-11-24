## Chapter 2

## Core prompt learning techniques

Prompt learning techniques play a crucial role in so-called “conversational programming,” the new paradigm of AI and software development that is now taking off. These techniques involve the strategic design of prompts, which are then used to draw out desired responses from large language models (LLMs).

Prompt engineering is the creative sum of all these techniques. It provides developers with the tools to guide, customize, and optimize the behavior of language models in conversational programming scenarios. Resulting prompts are in fact instrumental in guiding and tailoring responses to business needs, improving language understanding, and managing context.

Prompts are not magic, though. Quite the reverse. Getting them down is more a matter of trial and error than pure wizardry. Hence, at some point, you may end up with prompts that only partially address the very specific domain requests. This is where the need for fine-tuning emerges.

### What is prompt engineering?

As a developer, you use prompts as instructional input for the LLM. Prompts convey your intent and guide the model toward generating appropriate and contextually relevant responses that fulfill specific business needs. Prompts act as cues that inform the model about the desired outcome, the context in which it should operate, and the type of response expected. More technically, the prompt is the point from which the LLM begins to predict and then output new tokens.

#### Prompts at a glance

Let’s try some prompts with a particular LLM—specifically, GPT-3.5-turbo. Be aware, though, that LLMs are not deterministic tools, meaning that the response they give for the same input may be different every time.

![image](/api/v2/epubs/urn:orm:book:9780138280383/files/graphics/note.jpg) Note

Although LLMs are commonly described as non-deterministic, “seed” mode is now becoming more popular—in other words, seeding the model instead of sampling for a fully reproducible output.

##### A very basic prompt

The hello-world of prompt engineering—easily testable online on Bing Chat, ChatGPT, or something similar—can be as simple as what’s shown here:

```
During the week I
```

This prompt might result in something like the following output:

[Click here to view code image](ch02_images.xhtml#f0026-01)

```
During the week, I typically follow a structured routine.
```

Overall, the answer makes sense: The model tries to provide a continuation of the string, given the understood context.

Let’s try something a bit more specific:

[Click here to view code image](ch02_images.xhtml#f0026-02)

```
Complete the following sentence, as if you were Shakespeare.
During the week I
```

The subsequent output might be similar to:

[Click here to view code image](ch02_images.xhtml#f0026-03)

```
During the week, I doth engage in myriad tasks and endeavors, as the sun traverseth the sky with
unwavering pace.
```

So far so good.

##### A more complex prompt

One relatively complex prompt might be the following:

[Click here to view code image](ch02_images.xhtml#f0026-04)

```
'Unacceptable risk AI systems are systems considered a threat to people and will be banned. They
include:
-Cognitive behavioral manipulation of people or specific vulnerable groups: for example,
voice-activated toys that encourage dangerous behavior in children
-Social scoring: classifying people based on behavior, socio-economic status, or personal
characteristics
-Real-time and remote biometric identification systems, such as facial recognition
Some exceptions may be allowed: For instance, "post" remote biometric identification systems
where identification occurs after a significant delay will be allowed to prosecute serious
crimes but only after court approval.'
Given the above, extract only the forbidden AI applications and output them as json.
```

The model might now output the following JSON string:

[Click here to view code image](ch02_images.xhtml#f0026-05)

```
{
  "Forbidden AI Applications":[
    {
      "Application":"Cognitive behavioral manipulation of people or specific vulnerable groups",
      "Example": "Voice-activated toys that encourage dangerous behavior in children"
    },
    {
      "Application":"Social scoring",
      "Example":"Classifying on behavior, socio-economic status or personal characteristics"
    },
    {
      "Application":"Real-time and remote biometric identification systems",
      "Example":"Facial recognition"
    }
  ]
}
```

Encouraged by these first experiments, let’s try to outline some general rules for prompts.

##### General rules for prompts

A prompt can include context, instructions, input data, and optionally the structure of the desired output (also in the form of explicit examples). Depending on the task, you might need all four pieces or only a couple of them—most likely, instructions and input data.

Designing a prompt is an iterative process. Not surprisingly, the first reply you get from a model might be quite unreasonable. Don’t give up; just try again, but be more precise in what you provide, whether it’s plain instructions, input data, or context.

Two key points for a good prompt are specificity and descriptiveness.

- *Specificity* means designing prompts to leave as little room for interpretation as possible. By providing explicit instructions and restricting the operational space, developers can guide the language model to generate more accurate and desired outputs.
- *Descriptiveness* plays a significant role in effective prompt engineering. By using analogies and vivid descriptions, developers can provide clear instructions to the model. Analogies serve as valuable tools for conveying complex tasks and concepts, enabling the model to grasp the desired output with improved context and understanding.

##### General tips for prompting

A more technical tip is to use delimiters to clearly indicate distinct parts of the prompt. This helps the model focus on the relevant parts of the prompt. Usually, backticks or backslashes work well. For instance:

[Click here to view code image](ch02_images.xhtml#f0027-01)

```
Extract sentiment from the following text delimited by triple backticks: '''Great choice!'''
```

When the first attempt fails, two simple design strategies might help:

- Doubling down on instructions is useful to reinforce clarity and consistency in the model’s responses. Repetition techniques, such as providing instructions both before and after the primary content or using instruction-cue combinations, strengthen the model’s understanding of the task at hand.
- Changing the order of the information presented to the model. The order of information presented to the language model is significant. Whether instructions precede the content (`summarize the following`) or follow it (`summarize the preceding`) can lead to different results. Additionally, the order of few-shot examples (which will be covered shortly) can also introduce variations in the model’s behavior. This concept is known as recency bias.

One last thing to consider is an exit strategy for the model in case it fails to respond adequately. The prompt should instruct the model with an alternative path—in other words, an out. For instance, when asking a question about some documents, including a directive such as `write 'not found' if you can't find the answer within the document` or `check if the conditions are satisfied before answering` allows the model to gracefully handle situations in which the desired information is unavailable. This helps to avoid the generation of false or inaccurate responses.

#### Alternative ways to alter output

When aiming to align the output of an LLM more closely with the desired outcome, there are several options to consider. One approach involves modifying the prompt itself, following best practices and iteratively improving results. Another involves working with inner parameters (also called hyperparameters) of the model.

Beyond the purely prompt-based conversational approach, there are a few screws to tighten—comparable to the old-but-gold hyperparameters in the classic machine learning approach. These include the number of tokens, temperature, top_p (or nucleus) sampling, frequency penalties, presence penalties, and stop sequences.

##### Temperature versus top_p

Temperature (T) is a parameter that influences the level of creativity (or “randomness”) in the text generated by an LLM. The usual range of acceptable values is 0 to 2, but it depends on the specific model. When the temperature value is high (say, 0.8), the output becomes more diverse and imaginative. Conversely, a lower temperature (say, 0.1), makes the output more focused and deterministic.

Temperature affects the probability distribution of potential tokens at each step of the generation process. In practice, when choosing the next token, a model with a temperature of 0 will always choose the most probable one, while a model with a higher temperature will choose a token more or less randomly. A temperature of 0, therefore, would make the model entirely deterministic.

![image](/api/v2/epubs/urn:orm:book:9780138280383/files/graphics/note.jpg) Note

As discussed in [Chapter 1](ch01.xhtml#ch01), the temperature parameter works on the LLM’s last layer, being a parameter of the softmax function.

An alternative technique called top_p sampling (or nucleus sampling) is also useful for altering the default behavior of the LLM when generating the next token. With top_p sampling, instead of considering all possible tokens, the LLM focuses only on a subset of tokens (known as the nucleus) whose cumulative probability mass adds up to a specified threshold called top_p.

With top_p, the range of acceptable values is from 0 to 1. If, for instance, if the top_p value is set to 0.3, the language model will consider only tokens that contribute to the top 30% of the probability mass for the next token. This means lower top_p values limit the vocabulary of the model.

Both temperature and top_p sampling serve as powerful tools for controlling an LLM’s behavior, enabling different levels of creativity and control. They can be used independently or in combination, although it is generally recommended to alter only one at a time.

Adjusting these parameters makes them versatile for a wide range of applications. For instance, for a creative-writing task, a temperature of 1.3 (while also playing around with top_p) could be good, while for a code-generation task, 0.4 (again, while also experimenting with top_p) would be better.

Consider this prompt:

[Click here to view code image](ch02_images.xhtml#f0029-01)

```
Rephrase the following text:
<<<When aiming to align the output of a large language model (LLM) more closely with the desired
outcome, there are several options to consider. One approach involves modifying the prompt
itself, while another involves working with hyperparameters of the model>>>
```

With a temperature of 2, the prompt returns something like the following (which is grammatically incorrect):

[Click here to view code image](ch02_images.xhtml#f0029-02)

```
When attempting to have a large language model (LLM) output that reflects the desired outcome,
there are numerous alternatives to ponder. adapting the prompt itself is called one approach
that credits sustainability. Grounding on hyperparameters programs appertains settings amidst
the indicators simultaneously participates confidentiality impact later goals aren abbreviated
instructions. Otherwise instructions brings alternative ramification which doesn omit lengthy
resolution reaching goals which aren susceptible to evaluations constantly... likelihood
advancement adjustment exemplark.
```

With a temperature of 0, it returns the following:

[Click here to view code image](ch02_images.xhtml#f0029-03)

```
To achieve better alignment between the output of a language model (LLM) and the desired
outcome, there are various options to explore. One option is to adjust the prompt, while another
involves tweaking the model's hyperparameters.
```

In the middle, with a temperature of 0.8, the result looks like this:

[Click here to view code image](ch02_images.xhtml#f0029-04)

```
To achieve a greater degree of alignment between the output of a language model (LLM) and the
intended result, there are various approaches to consider. One tactic involves adjusting the
prompt directly, whereas an alternative involves manipulating the model's hyperparameters.
```

##### Frequency and presence penalties

Another set of parameters is the frequency and presence penalty. These add a penalty when calculating probability of the next token. This results in a recalculation of each probability, which ultimately affects which token is chosen.

The frequency penalty is applied to tokens that have already been mentioned in the preceding text (including the prompt). It is scaled based on the number of times the token has appeared. For example, a token that has appeared five times receives a higher penalty, reducing its likelihood of appearing again, than a token that has appeared only once. The presence penalty, on the other hand, applies a penalty to tokens regardless of their frequency. Once a token has appeared at least once before, it will be subject to the penalty. The range of acceptable values for both is from –2 to 2.

These parameter settings are valuable for eliminating (or promoting, in the case of negative values) repetitive elements from generated outputs. For instance, consider this prompt:

[Click here to view code image](ch02_images.xhtml#f0030-01)

```
Rephrase the following text:
<<<When aiming to align the output of a large language model (LLM) more closely with the desired
outcome, there are several options to consider. One approach involves modifying the prompt
itself, while another involves working with hyperparameters of the model>>>
```

With a frequency penalty of 2, it returns something like:

[Click here to view code image](ch02_images.xhtml#f0030-02)

```
To enhance the accuracy of a large language model's (LLM) output to meet the desired result,
there are various strategies to explore. One method involves adjusting the prompt itself,
whereas another entails manipulating the model's hyperparameters.
```

While with a frequency penalty of 0, it returns something like:

[Click here to view code image](ch02_images.xhtml#f0030-03)

```
There are various options to consider when attempting to better align the output of a language
model (LLM) with the desired outcome. One option is to modify the prompt, while another is to
adjust the model's hyperparameters.
```

##### Max tokens and stop sequences

The max tokens parameter specifies the maximum number of tokens that can be generated by the model, while the stop sequence parameter instructs the language model to halt the generation of further content. Stop sequences are in fact an additional mechanism for controlling the length of the model’s output.

![image](/api/v2/epubs/urn:orm:book:9780138280383/files/graphics/note.jpg) Note

The model is limited by its inner structure. For instance, GPT-4 is limited to a max number of 32,768 tokens, including the entire conversation and prompts, while GPT-4-turbo has a context window of 128k tokens.

Consider the following prompt:

```
Paris is the capital of
```

The model will likely generate `France`. If a full stop (.) is designated as the stop sequence, the model will cease generating text when it reaches the end of the first sentence, regardless of the specified token limit.

A more complex example can be built with a few-shot approach, which uses a pair of angled brackets (`<<` … `>>`) on each end of a sentiment. Considering the following prompt:

[Click here to view code image](ch02_images.xhtml#f0030-04)

```
Extract sentiment from the following tweets:
Tweet: I love this match!
Sentiment: <<positive>>
Tweet: Not sure I completely agree with you
Sentiment: <<neutral>>
Tweet: Amazing movie!!!
Sentiment:
```

Including the angled brackets instructs the model to stop generating tokens after extracting the sentiment.

By using stop sequences strategically within prompts, developers can ensure that the model generates text up to a specific point, preventing it from producing unnecessary or undesired information. This technique proves particularly useful in scenarios where precise and limited-length responses are desired, such as when generating short summaries or single-sentence outputs.

#### Setting up for code execution

Now that you’ve learned the basic theoretical background of prompting, let’s bridge the gap between theory and practical implementation. This section transitions from discussing the intricacies of prompt engineering to the hands-on aspect of writing code. By translating insights into executable instructions, you’ll explore the tangible outcomes of prompt manipulation.

In this section, you’ll focus on OpenAI models, like GPT-4, GPT-3.5-turbo, and their predecessors. (Other chapters might use different models.) For these examples, .NET and C# will be used mainly, but Python will also be used at some point.

##### Getting access to OpenAI APIs

To access OpenAI APIs, there are multiple options available. You can leverage the REST APIs from OpenAI or Azure OpenAI, the Azure OpenAI .NET or Python SDK, or the OpenAI Python package.

In general, Azure OpenAI Services enable Azure customers to use those advanced language AI models, while still benefiting from the security and enterprise features offered by Microsoft Azure, such as private networking, regional availability, and responsible AI content filtering.

At first, directly accessing OpenAI could be the easiest choice. However, when it comes to enterprise implementations, Azure OpenAI is the more suitable option due to its alignment with the Azure platform and its enterprise-grade features.

To get started with Azure OpenAI, your Azure subscription must include access to Azure OpenAI, and you must set up an Azure OpenAI Service resource with a deployed model.

If you choose to use OpenAI directly, you can create an API key on the developer site (*[https://platform.openai.com/](https://platform.openai.com/)*).

In terms of technical differences, OpenAI uses the `model` keyword argument to specify the desired model, whereas Azure OpenAI employs the `deployment_id` keyword argument to identify the specific model deployment to use.

##### Chat Completion API versus Completion API

OpenAI APIs offer two different approaches for generating responses from language models: the Chat Completion API and the Completion API. Both are available in two modes: a standard form, which returns the complete output once ready, and a streaming version, which streams the response token by token.

The Chat Completion API is designed for chat-like interactions, where message history is concatenated with the latest user message in JSON format, allowing for controlled completions. In contrast, the Completion API provides completions for a single prompt and takes a single string as input.

The back-end models used for the two APIs differ:

- The Chat Completion API supports GPT-4-turbo, GPT-4, GPT-4-0314, GPT-4-32k, GPT-4-32k-0314, GPT-3.5-turbo, and GPT-3.5-turbo-0301.
- The Completion API includes older (but still good for some use cases) models, such as text-davinci-003, text-davinci-002, text-curie-001, text-babbage-001, and text-ada-001.

One advantage of the Chat Completion API is the role selection feature, which enables users to assign roles to different entities in the conversation, such as user, assistant, and, most importantly, system. The first system message provides the model with the main context and instructions “set in stone.” This helps in maintaining consistent context throughout the interaction. Moreover, the system message helps set the behavior of the assistant. For example, you can modify the personality or tone of the assistant or give specific instructions on how it should respond. Additionally, the Chat Completion API allows for longer conversational context to be appended, enabling a more dynamic conversation flow. In contrast, the Completion API does not include the role selection or conversation formatting features. It takes a single prompt as input and generates a response accordingly.

Both APIs provide `finish_reasons` in the response to indicate the completion status. Possible `finish_reasons` values include `stop` (complete message or a message terminated by a stop sequence), `length` (incomplete output due to token limits), `function_call` (model calling a function), `content_filter` (omitted content due to content filters), and `null` (response still in progress).

Although OpenAI recommends the Chat Completion API for most use cases, the raw Completion API sometimes offers more potential for creative structuring of requests, allowing users to construct their own JSON format or other formats. The JSON output can be forced in the Chat Completion API by using the JSON mode with the `response_format` parameter set to `json_object`.

To summarize, the Chat Completion API is a higher-level API that generates an internal prompt and calls some lower-level API and is suited for chat-like interactions with role selection and conversation formatting. In contrast, the Completion API is focused on generating completions for individual prompts.

It’s worth mentioning that the two APIs are to some extent interchangeable. That is, a user can force the format of a Chat Completion response to reflect the format of a Completion response by constructing a request using a single user message. For instance, one can translate from English to Italian with the following Completion prompt:

[Click here to view code image](ch02_images.xhtml#f0032-01)

```
Translate the following English text to Italian: "{input}"
```

An equivalent Chat Completion prompt would be:

[Click here to view code image](ch02_images.xhtml#f0032-02)

```
[{"role": "user", "content": 'Translate the following English text to Italian: "{input}"'}]
```

Similarly, a user can use the Completion API to mimic a conversation between a user and an assistant by appropriately formatting the input.

##### Setting things up in C#

You can now set things up to use Azure OpenAI API in Visual Studio Code through interactive .NET notebooks, which you will find in the source code that comes with this book. The model used is GPT-3.5-turbo. You set up the necessary NuGet package—in this case, Azure.AI.OpenAI—with the following line:

[Click here to view code image](ch02_images.xhtml#f0033-01)

```
#r "nuget: Azure.AI.OpenAI, 1.0.0-beta.12"
```

Then, moving on with the C# code:

[Click here to view code image](ch02_images.xhtml#f0033-02)

```
using System;
using Azure.AI.OpenAI;
var AOAI_ENDPOINT = Environment.GetEnvironmentVariable("AOAI_ENDPOINT");
var AOAI_KEY = Environment.GetEnvironmentVariable("AOAI_KEY");
var AOAI_DEPLOYMENTID = Environment.GetEnvironmentVariable("AOAI_DEPLOYMENTID");
var AOAI_chat_DEPLOYMENTID = Environment.GetEnvironmentVariable("AOAI_chat_DEPLOYMENTID");
var endpoint = new Uri(AOAI_ENDPOINT);
var credentials = new Azure.AzureKeyCredential(AOAI_KEY);
var openAIClient = new OpenAIClient(endpoint, credentials);
var completionOptions = new ChatCompletionsOptions
{
    DeploymentName=AOAI_DEPLOYMENTID,
    MaxTokens=500,
    Temperature=0.7f,
    FrequencyPenalty=0f,
    PresencePenalty=0f,
    NucleusSamplingFactor=1,
    StopSequences={}
};

var prompt =
    @"rephrase the following text: <<<When aiming to align the output of a language model (LLM)
more closely with the desired outcome, there are several options to consider. One approach
involves modifying the prompt itself, while another involves working with hyperparameters of the
model>>>";

completionOptions.Messages.Add(new ChatRequestUserMessage (prompt));
var response = await openAIClient.GetChatCompletionsAsync(completionOptions);
var completions = response.Value;
completions.Choices[0].Message.Content.Display();
```

After running this code, one possible output displayed in the notebook is as follows:

[Click here to view code image](ch02_images.xhtml#f0033-03)

```
There are various ways to bring the output of a language model (LLM) closer to the intended
result. One method is to adjust the prompt, while another involves tweaking the model's
hyperparameters.
```

Note that the previous code uses the Chat Completion version of the API. A similar result could have been obtained through the following code, which uses the Completion API and an older model:

[Click here to view code image](ch02_images.xhtml#f0034-01)

```
var completionOptions = new CompletionsOptions
{
   DeploymentName=AOAI_DEPLOYMENTID,
   Prompts={prompt},
   MaxTokens=500,
   Temperature=0.2f,
   FrequencyPenalty=0.0f,
   PresencePenalty=0.0f,NucleusSamplingFactor=1,
   StopSequences={"."}
};
Completions response = await openAIClient.GetCompletionsAsync(completionOptions);
response.Choices.First().Text.Display();
```

##### Setting things up in Python

If you prefer working with Python, put the following equivalent code in a Jupyter Notebook:

[Click here to view code image](ch02_images.xhtml#f0034-02)

```
import os
import openai
from openai import AzureOpenAI
from dotenv import load_dotenv, find_dotenv
_ = load_dotenv(find_dotenv()) # read local .env file

client = AzureOpenAI(
  azure endpoint = os.getenv("AZURE OPENAI ENDPOINT"),
  api key=os.getenv("AZURE OPENAI KEY"),
  openai.api_version="2023-09-01-preview"
)
deployment_name=os.getenv("AOAI_DEPLOYMENTID")
context = [ {'role':'user', 'content':"rephrase the following text: 'When aiming to align the
output of a language model (LLM) more closely with the desired outcome, there are several
options to consider: one approach involves modifying the prompt itself, while another involves
working with hyperparameters of the model.'"} ]
response = client.chat.completions.create(
                       model=deployment_name,
                       messages=context,
                       temperature=0.7)
response.choices[0].message["content"]
```

This is based on OpenAI Python SDK v.1.6.0, which can be installed via `pip install openai.`

### Basic techniques

Prompt engineering involves understanding the fundamental behavior of LLMs to construct prompts effectively. Prompts consist of different components: instructions, primary content, examples, cues, and supporting content (also known as additional context or knowledge). Instructions guide the model on what to do, while primary content is the main text being processed. Examples provide desired behavior demonstrations, while cues act as a jumpstart for the model’s output. Supporting content provides additional information to influence the output, such as knowledge to search for before answering. By strategically combining these elements, you can design prompts that elicit the desired responses from the model.

This section covers basic techniques for mastering the art of prompting.

#### Zero-shot scenarios

Whenever a task, assigned to a model through a prompt, is given without any specific example of the desired output, it’s called *zero-shot prompting*. Basic scenarios might include:

- **Proper text completion** For example, writing an email or a medical record
- **Topic extraction** For example, to classify customers’ emails
- **Translations and sentiment analysis** For example, to label as positive/negative a tweet or to translate users’ reviews to the same language
- **Style-impersonation** For example, Shakespeare, Hemingway, or any other notorious personality the model may have been trained on.

##### The basic theory

Given the huge amount of data that LLMs are trained on, these models can perform an increasing number of “zero-shot” tasks. In fact, the model already knows how to act in those cases. It has incorporated the ability to perform these tasks during its considerable training. However, the more clarity expressed in the prompt, the more effective and accurate the output will be.

![image](/api/v2/epubs/urn:orm:book:9780138280383/files/graphics/note.jpg) Note

Clear prompts might not be short. In many situations, longer prompts provide more clarity and context.

##### A few examples

A basic example of a zero-shot prompt might look like this:

[Click here to view code image](ch02_images.xhtml#f0035-01)

```
Extract sentiment from the following text delimited by triple backticks.
'''Language models have revolutionized the way we interact with technology, empowering us to
generate creative content, explore new ideas, and enhance our communication. LLMs offer immense
potential for unlocking innovation and improving various aspects of our lives, opening up
exciting possibilities for the future.'''
```

An output would be:

[Click here to view code image](ch02_images.xhtml#f0035-02)

```
The sentiment of the provided text is positive.
```

Trying topic extractions, it would be:

[Click here to view code image](ch02_images.xhtml#f0035-03)

```
Determine at most three topics that are being discussed in the following text, delimited by
triple backticks.

'''Language models have revolutionized the way we interact with technology, empowering us to
generate creative content, explore new ideas, and enhance our communication. LLMs offer immense
potential for unlocking innovation and improving various aspects of our lives, opening up
exciting possibilities for the future.'''
```

Here’s a possible resulting output:

[Click here to view code image](ch02_images.xhtml#f0036-01)

```
The three topics discussed in the text are:
The impact of language models on technology interaction: Language models have revolutionized the
way we interact with technology, enabling us to generate creative content, explore new ideas,
and enhance communication.
The potential of LLMs for innovation: LLMs offer immense potential for unlocking innovation and
improving various aspects of our lives. They open up exciting possibilities for the future.
Benefits and improvements in various aspects of life: The text highlights how LLMs can enhance
communication, generate creative content, and explore new ideas, thereby improving different
aspects of our lives.
```

##### Iterative refining

Prompt engineering is a matter of refining. Trying to improve the preceding result, you might want to explicitly list the sentiment the model should output and to limit the output to the sentiment only. For example, a slightly improved prompt might look like the following:

[Click here to view code image](ch02_images.xhtml#f0036-02)

```
Extract sentiment (positive, neutral, negative, unknown) from the following text, delimited by
triple backticks.
'''Language models have revolutionized the way we interact with technology, empowering us to
generate creative content, explore new ideas, and enhance our communication. LLMs offer immense
potential for unlocking innovation and improving various aspects of our lives, opening up
exciting possibilities for the future.'''
Return only one word indicating the sentiment.
```

This would result in the following output:

```
Positive
```

Likewise, regarding the topic extraction, you might want only one or two words per topic, each separated by commas:

[Click here to view code image](ch02_images.xhtml#f0036-03)

```
Determine at most three topics that are being discussed in the following text, delimited by
triple backticks.
Format the response as a list of at most 2 words, separated by commas.
'''Language models have revolutionized the way we interact with technology, empowering us to
generate creative content, explore new ideas, and enhance our communication. LLMs offer immense
potential for unlocking innovation and improving various aspects of our lives, opening up
exciting possibilities for the future.'''
```

The result would look like:

[Click here to view code image](ch02_images.xhtml#f0036-04)

```
Language models, Interaction with technology, LLM potential.
```

#### Few-shot scenarios

Zero-shot capabilities are impressive but face important limitations when tackling complex tasks. This is where few-shot prompting comes in handy. Few-shot prompting allows for in-context learning by providing demonstrations within the prompt to guide the model’s performance.

A few-shot prompt consists of several examples, or *shots*, which condition the model to generate responses in subsequent instances. While a single example may suffice for basic tasks, more challenging scenarios call for increasing numbers of demonstrations.

When using the Chat Completion API, few-shot learning examples can be included in the system message or, more often, in the messages array as user/assistant interactions following the initial system message.

![image](/api/v2/epubs/urn:orm:book:9780138280383/files/graphics/note.jpg) Note

Few-shot prompting is useful if the accuracy of the response is too low. (Measuring accuracy in an LLM context is covered later in the book.)

##### The basic theory

The concept of few-shot (or in-context) learning emerged as an alternative to fine-tuning models on task-specific datasets. Fine-tuning requires the availability of a base model. OpenAI’s available base models are GPT-3.5-turbo, davinci, curie, babbage, and ada, but not the latest GPT-4 and GPT-4-turbo models. Fine-tuning also requires a lot of well-formatted and validated data. In this context, developed as LLM sizes grew significantly, few-shot learning offers advantages over fine-tuning, reducing data requirements and mitigating the risk of overfitting, typical of any machine learning solution.

This approach focuses on priming the model for inference within specific conversations or contexts. It has demonstrated competitive performance compared to fine-tuned models in tasks like translation, question answering, word unscrambling, and sentence construction. However, the inner workings of in-context learning and the contributions of different aspects of shots to task performance remain less understood.

Recent research has shown that ground truth demonstrations are not essential, as randomly replacing correct labels has minimal impact on classification and multiple-choice tasks. Instead, other aspects of demonstrations, such as the label space, input text distribution, and sequence format, play crucial roles in driving performance. For instance, the two following prompts for sentiment analysis—the first with correct labels, and the second with completely wrong labels —offer similar performance.

[Click here to view code image](ch02_images.xhtml#f0037-01)

```
Tweet: "I hate it when I have no wifi"
Sentiment: Negative
Tweet: "Loved that movie"
Sentiment: Positive
Tweet: "Great car!!!"
Sentiment: Positive

Tweet: {new tweet}
Sentiment:
```

And:

[Click here to view code image](ch02_images.xhtml#f0038-01)

```
Tweet: "I hate it when I have no wifi"
Sentiment: Positive
Tweet: "Loved that movie"
Sentiment: Negative
Tweet: "Great car!!!"
Sentiment: Negative

Tweet: {new tweet}
Sentiment:
```

In-context learning may struggle with tasks that lack precaptured input-label correspondence. This suggests that the intrinsic ability to perform a task is obtained during training, with demonstrations (or shots) primarily serving as a task locator.

##### A few examples

One of the most famous examples of the efficiency of few-shot learning prompts is one taken from a paper by Brown et al. (2020), where the task is to correctly use a new word in a sentence:

[Click here to view code image](ch02_images.xhtml#f0038-02)

```
A "whatpu" is a small, furry animal native to Tanzania. An example of a sentence that uses
the word whatpu is: We were traveling in Africa and we saw these very cute whatpus. To do a
"farduddle" means to jump up and down really fast. An example of a sentence that uses the word
farduddle is:
```

The model would correctly output something like:

[Click here to view code image](ch02_images.xhtml#f0038-03)

```
We were so excited that we couldn't help but farduddle when our favorite team won the
championship.
```

A very good use case for few-shot learning is writing something in a given style, such as code documentation or social media posts. Whenever there is a pattern or a format, and explaining it is more complex than showing it, it’s worth trying few-shot prompting. For instance, the following prompt would generate a consistent documentation:

[Click here to view code image](ch02_images.xhtml#f0038-04)

```
/// <summary>
/// Returns detailed information about a specific event
/// </summary>
/// <param name="org">Name of the organization</param>
/// <param name="year">Year of the event</param>
/// <param name="tournamentId">Internal ID of the event</param>
/// <returns>Detailed info about the event</returns>
/// <remarks>Sample events to try are: 2892, 2331, 1028. Try also 8392.
/// If any of the parameters are invalid, the endpoint returns 404.</remarks>
public IActionResult Tournament(string org, int? year, string eventId)

public IActionResult Team(string org, string teamId)
```

Based on the model version and the API (Completion or Chat Completion), the system might tend to explain the code and the documentation instead of producing new documentation for the presented method (`IActionResult Team`). That’s why a better and more precise prompt would be the following, which includes specific instructions:

[Click here to view code image](ch02_images.xhtml#f0039-01)

```
Your task is to generate documentation in a consistent style.
/// <summary>
/// Returns detailed information about a specific event
/// </summary>
/// <param name="org">Name of the organization</param>
/// <param name="year">Year of the event</param>
/// <param name="tournamentId">Internal ID of the event</param>
/// <returns>Detailed info about the event</returns>
/// <remarks>Sample events to try are: 2892, 2331, 1028. Try also 8392.
/// If any of the parameters are invalid, the endpoint returns 404.</remarks>
public IActionResult Tournament(string org, int? year, string eventId)

public IActionResult Team(string org, string teamId)
```

##### Iterative refining

The last prompt is likely to generate a similar response:

[Click here to view code image](ch02_images.xhtml#f0039-02)

```
/// <summary>
/// Returns detailed information about a specific event.
/// </summary>
/// <param name="org">The name of the organization.</param>
/// <param name="year">The year of the event.</param>
/// <param name="tournamentId">The internal ID of the event.</param>
/// <returns>Detailed information about the event.</returns>
/// <remarks>
/// Sample event IDs to try are: 2892, 2331, 1028. You can also try 8392.
/// If any of the parameters are invalid, the endpoint returns a 404 error.
/// </remarks>
public IActionResult Event(string org, int? year, string eventId) {
// Implementation code here
}
/// <summary>
/// Retrieves information about a specific team.
 /// </summary>
/// <param name="org">The name of the organization.</param>
/// <param name="teamId">The ID of the team.</param>
/// <returns>Information about the team.</returns>
public IActionResult Team(string org, string teamId) {
// Implementation code here
}
The Event method is an action that returns detailed information about a specific event. It takes
three parameters: org (representing the name of the organization), year (representing the year
of the event, nullable), and eventId (representing the internal ID of the event). This method
should be called to retrieve detailed information about an event.
The Team method is another action that retrieves information about a specific team. It takes two
parameters: org (representing the name of the organization) and teamId (representing the ID of
the team). This method should be called to fetch information about a team.
```

As is easily observable from the previous examples, all these generative models want to write text. This is reasonable because they were trained to predict the next token. It is very likely, then, that a good prompt needs to incorporate something to restrict the output.

Following up with the last example, a better prompt might be:

[Click here to view code image](ch02_images.xhtml#f0040-01)

```
Your task is to generate code comments in a consistent style with the reference. The response
must include only the comments for the new method, without any additional explanation or
comment.

Style reference:

/// <summary>
/// Returns detailed information about a specific event
/// </summary>
/// <param name="org">Name of the organization</param>
/// <param name="year">Year of the event</param>
/// <param name="tournamentId">Internal ID of the event</param>
/// <returns>Detailed info about the event</returns>
/// <remarks>Sample events to try are: 2892, 2331, 1028. Try also 8392.
/// If any of the parameters are invalid, the endpoint returns 404.</remarks>
public IActionResult Tournament(string org, int? year, string eventId)

New method:

public IActionResult Team(string org, string teamId)
```

This might still output some additional explanation:

[Click here to view code image](ch02_images.xhtml#f0040-02)

```
/// <summary>
/// Returns detailed information about a specific team.
/// </summary>
/// <param name="org">Name of the organization</param>
/// <param name="teamId">ID of the team</param>
/// <returns>Detailed info about the team</returns>

Please note that this is the code comment for the new Team method. It retrieves detailed
information about a specific team. The method takes two parameters: org, which represents the
name of the organization, and teamId, which is the ID of the team. The method returns detailed
information about the team.
```

At this point, to prevent the model from producing additional text, you might need a different strategy: asking the model to check if certain conditions on the output are satisfied. This can be done by appending this line to the former prompt:

[Click here to view code image](ch02_images.xhtml#f0040-03)

```
Check if the output contains additional text and, if so, remove it.
```

Asking the model to check if certain conditions in the input are satisfied is a very useful technique. It can also be exploited for more standard tasks, such as form or json/xml/html validation.

In this case, you also tried to validate the output text. This is more of a trick than a technique because the model doesn’t really produce the full output to be validated. Still, it works as a guardrail. A better way to achieve the same result would have been to add one more API call with the former prompt or, as explored later in book, involving a framework like Microsoft Guidance or Guardrails AI.

Considering this, it’s important to stress that these models work better when they are told what they need to do instead of what they must avoid.

#### Chain-of-thought scenarios

While standard few-shot prompting is effective for many tasks, it is not without limitations—particularly when it comes to more intricate reasoning tasks, such as mathematical and logical problems, as well as tasks that require the execution of multiple sequential steps.

![image](/api/v2/epubs/urn:orm:book:9780138280383/files/graphics/note.jpg) Note

Later models such as GPT-4 perform noticeably better on logical problems, even with simple non-optimized prompts.

When few-shot prompting proves insufficient, it may indicate the need for fine-tuning models (if these are an option, which they aren’t for GPT-4 and GPT-4-turbo) or exploring advanced prompting techniques. One such technique is chain-of-thought (CoT) prompting. You use CoT prompting to track down all the steps (thoughts) performed by the model to draw the solution.

As presented in the work of Wei et al. (2022), this technique gives the model time to think, enhancing reasoning abilities by incorporating intermediate reasoning steps. When used in conjunction with few-shot prompting, it leads to improved performance on intricate tasks that demand prior reasoning for accurate responses.

![image](/api/v2/epubs/urn:orm:book:9780138280383/files/graphics/note.jpg) Note

The effectiveness of CoT prompting is observed primarily when employed with models consisting of approximately 100 billion parameters. Smaller models tend to generate incoherent chains of thought, resulting in lower accuracy compared to standard prompting. The performance improvements achieved through CoT prompting generally scale with the size of the model.

##### The basic theory

Anyone young enough to remember their days as a student will know that during exams, the brain stops functioning. Most of the time, one tries to answer the professor’s question, almost guessing the solution, without really thinking about it. LLMs do the same thing. Sometimes they continue the sentence without thinking; they just make a guess.

The basic idea behind CoT is to instruct the model to take time to think, allowing it to reconstruct the reasoning steps during response generation. This simple idea significantly enhances the model’s ability to perform complex tasks. This makes sense when you consider how language models produce responses. They attempt to predict the next token, so the more intermediate “reasoning” tokens they generate, the more the model needs to establish coherence among them and, ideally, provide a correct response.

![image](/api/v2/epubs/urn:orm:book:9780138280383/files/graphics/note.jpg) Note

By only asking the model for the final answer, you leave limited room for the model to verify the coherence between the question (prompt) and its response; in contrast, explicitly outlining all the steps helps the model find the logical thread.

##### A few examples

Following the professor-student example, the first two attempts to improve the output of the model might be the classical “make sure the answer is correct” or “let’s think step by step” approach. For instance, consider the following easy problem:

[Click here to view code image](ch02_images.xhtml#f0042-01)

```
I bought 20 pens, gave 12 pens to my son, 3 to my daughter, 1 to my mom. I then bought 4 more
pens and lost 1.
Output the number of pens I have now.
```

Regarding logical problems, temperature and model version definitely matter. Lower temperature will keep things more deterministic, while the latest models will have better accuracy, because they have been trained on a larger dataset for logical problems.

With a temperature of 0.2, a GPT-3.5-turbo model will provide an answer like the following, whereas a GPT-4 model will probably say, “You currently have 7 pens”:

[Click here to view code image](ch02_images.xhtml#f0042-02)

```
I have 8 pens now.
Explanation: Initially, I had 20 pens. I gave away 12 + 3 + 1 = 16 pens. So I had 20 - 16 = 4
pens left. Then I bought 4 more pens, so I had 4 + 4 = 8 pens. But I lost 1 pen, so I have
8 - 1 = 7 pens. Therefore, the output is 8 pens.
```

![image](/api/v2/epubs/urn:orm:book:9780138280383/files/graphics/note.jpg) Note

Older models would have probably responded with the number only, without any reasoning. Newer models have been reinforced through step-by-step prompting.

The answer is wrong. Worse, the answer is incoherent. It says 8, while it correctly calculates 7.

Let’s try the following prompt to see if it provides more reasonable output:

[Click here to view code image](ch02_images.xhtml#f0042-03)

```
I bought 20 pens, gave 12 pens to my son, 3 to my daughter, 1 to my mom. I then bought 4 more
pens and lost 1.
Output the number of pens I have now and make sure the answer is correct and coherent. Make sure
the answer and the explanation are correct and coherent before answering.
```

Here, the output is as follows:

[Click here to view code image](ch02_images.xhtml#f0042-04)

```
After buying 20 pens, I had 20 pens. After giving 12 pens to my son, I had 8 pens. After giving
3 pens to my daughter, I had 5 pens. After giving 1 pen to my mom, I had 4 pens. After buying 4
more pens, I had 8 pens. After losing 1 pen, I had 7 pens.
Therefore, I have 7 pens now.
```

That’s correct.

An equivalent prompt might have been:

[Click here to view code image](ch02_images.xhtml#f0042-05)

```
I bought 20 pens, gave 12 pens to my son, 3 to my daughter, 1 to my mom. I then bought 4 more
pens and lost 1.
Output the number of pens I have now. Let's think it step by step.
```

And the output:

[Click here to view code image](ch02_images.xhtml#f0043-01)

```
1. Start with 20 pens.
2. Gave 12 pens to my son, so I have 20 - 12 = 8 pens left.
3. Gave 3 pens to my daughter, so I have 8 - 3 = 5 pens left.
4. Gave 1 pen to my mom, so I have 5 - 1 = 4 pens left.
5. Bought 4 more pens, so I have 4 + 4 = 8 pens now.
6. Lost 1 pen, so I have 8 - 1 = 7 pens now.
Therefore, I have 7 pens now.
```

This is called a zero-shot chain-of-thought prompt; the magic sentence, “Let’s think it step by step,” forces the model to take time to think and to write down all the steps.

At this point, to get the final answer, you could ask the model to produce a structured output or make one more API call with a simple prompt like, “Extract only the final answer from this text”:

[Click here to view code image](ch02_images.xhtml#f0043-02)

```
I bought 20 pens, gave 12 pens to my son, 3 to my daughter, 1 to my mom. I then bought 4 more
pens and lost 1.
Output the number of pens I have now. Let's think it step by step. Output a json with:
explanation (string) and result (int).
```

The result would look like:

[Click here to view code image](ch02_images.xhtml#f0043-03)

```
{"explanation":"Initially, I had 20 pens. After giving 12 to my son, I had 8 left. Then, I gave
3 to my daughter, leaving me with 5. Giving 1 to my mom left me with 4 pens. Buying 4 more pens
gave me a total of 8 pens. Unfortunately, I lost 1 pen, leaving me with a final total of 7
pens.","result":7}
```

##### Possible extensions

Combining the few-shot technique with the chain-of-thought approach can give the model some examples of step-by-step reasoning to emulate. This is called *few-shot chain-of-thought*. For instance:

[Click here to view code image](ch02_images.xhtml#f0043-04)

```
Which is the more convenient way to reach the destination, balancing costs and time?
Option 1: Take a 20-minute walk, then a 15-minute bus ride (2 dollars), and finally a 5-minute
taxi ride (15 dollars).
Option 2: Take a 30-minute bike ride, then a 10-minute subway ride (2 dollars), and finally a
5-minute walk.

Option 1 will take 20 + 15 + 5 = 40 minutes. Option 1 will cost 17 dollars.
Option 2 will take 30 + 10 + 5 = 45 minutes. Option 2 will cost 2 dollars.
Since Option 1 takes 40 minutes and Option 2 takes 45 minutes, Option 1 is quicker, but Option 2
is cheaper by far. Option 2 is better.

Which is the better way to get to the office?
Option 1: 40 minutes train (5 dollars), 15 mins walk
Option 2: 10-minutes taxi ride (15 dollars), 10-minutes subway (2 dollars), 2-mins walk
```

An extension of this basic prompting technique is Auto-CoT. This basically leverages the few-shot CoT approach, using a prompt to generate more samples (shots) of reasoning, which are then concatenated into a final prompt. Essentially, the idea is to auto-generate a few-shot CoT prompt.

Beyond chain-of-thought prompting, there is one more sophisticated idea: tree of thoughts. This technique can be implemented in essentially two ways. The first is through a single prompt, like the following:

[Click here to view code image](ch02_images.xhtml#f0044-01)

```
Consider a scenario where three experts approach this question.
Each expert will contribute one step of their thought process and share it with the group.
Subsequently, all experts will proceed to the next step.
If any expert realizes they have made a mistake at any stage, they will exit the process.
The question is the following: {question}
```

A more sophisticated approach to tree of thoughts requires writing some more code, with different prompts running (maybe also with different temperatures) and producing reasoning paths. These paths are then evaluated by another model instance with a scoring/voting prompt, which excludes wrong ones. At the end, a certain mechanism votes (for coherence or majority) for the correct answer.

A few more emerging but relatively easy-to-implement prompting techniques are analogical prompting (by Google DeepMind), which asks the model to recall a similar problem before solving the current one; and step-back prompting, which prompts the model to step back from the specific instance and contemplate the general principle at hand.

### Fundamental use cases

Having explored some more intricate techniques, it’s time to shift the focus to practical applications. In this section, you’ll delve into fundamental use cases where these techniques come to life, demonstrating their effectiveness in real-world scenarios. Some of these use cases will be expanded in later chapters, including chatbots, summarization and expansion, coding helpers, and universal translators.

#### Chatbots

Chatbots have been around for years, but until the advent of the latest language models, they were mostly perceived as a waste of time by users who had to interact with them. However, these new models are now capable of understanding even when the user makes mistakes or writes poorly, and they respond coherently to the assigned task. Previously, the thought of people who used chatbots was almost always, “Let me talk to a human; this bot doesn’t understand.” Soon, however, I expect we will reach something like the opposite: “Let me talk to a chatbot; this human doesn’t understand.”

##### System messages

With chatbots, system messages, also known as *metaprompts*, can be used to guide the model’s behavior. A metaprompt defines the general guidelines to be followed. Still, while using these templates and guidelines, it remains essential to validate the responses generated by the models.

A good system prompt should define the model’s profile, capabilities, and limitations for the specific scenario. This involves:

- Specifying how the model should complete tasks and whether it can use additional tools
- Clearly outlining the scope and limitations of the model’s performance, including instructions for off-topic or irrelevant prompts
- Determining the desired posture and tone for the model’s responses
- Defining the output format, including language, syntax, and any formatting preferences
- Providing examples to demonstrate the model’s intended behavior, considering difficult use cases and CoT reasoning
- Establishing additional behavioral guardrails by identifying, prioritizing, and addressing potential harms

##### Collecting information

Suppose you want to build a booking chatbot for a hotel brand group. A reasonable system prompt might look something like this:

[Click here to view code image](ch02_images.xhtml#f0045-01)

```
You are a HotelBot, an automated service to collect hotel bookings within a hotel brand group,
in different cities.

You first greet the customer, then collect the booking, asking the name of the customer, the
city the customer wants to book, room type and additional services.
You wait to collect the entire booking, then summarize it and check for a final time if the
customer wants to add anything else.

You ask for arrival date, departure date, and calculate the number of nights. You ask for a
passport number. Make sure to clarify all options and extras to uniquely identify the item from
the pricing list.
You respond in a short, very conversational friendly style. Available cities: Rome, Lisbon,
Bucharest.

The hotel rooms are:
single 150.00 per night
double 250 per night
suite 350 per night

Extra services:
parking 20.00 per day,
late checkout 100.00
airport transfer 50.00
SPA 30.00 per day
```

Consider that the previous prompt is only a piece of a broader application. After the system message is launched, the application should ask the user to start an interaction; then, a proper conversation between the user and chatbot should begin.

For a console application, this is the basic code to incorporate to start such an interaction:

[Click here to view code image](ch02_images.xhtml#f0045-02)

```
var chatCompletionsOptions = new ChatCompletionsOptions
{
         DeploymentName = AOAI_chat_DEPLOYMENTID
         Messages =
         {
                  new ChatRequestSystemMessage(systemPrompt),
                  new ChatRequestUserMessage("Introduce yourself"),
          }
};
while (true)
{
         Console.WriteLine();
         Console.Write("HotelBot: ");
         var chatCompletionsResponse = await openAIClient.GetChatCompletionsAsync(chatCompletions
Options);
         var chatMessage = chatCompletionsResponse.Value.Choices[0].Message;
         Console.Write(chatMessage.Content);
         chatCompletionsOptions.Messages.Add(new ChatRequestAssistantMessage(chatMessage.
Content));
         Console.WriteLine();
         Console.Write("Enter a message: ");
         var userMessage = Console.ReadLine();
         chatCompletionsOptions.Messages.Add(new ChatRequestUserMessage(userMessage));
}
```

![image](/api/v2/epubs/urn:orm:book:9780138280383/files/graphics/note.jpg) Note

When dealing with web apps, you must also consider the UI of the chat.

##### Summarization and transformation

Now that you have a prompt to collect a hotel booking, the hotel booking system will likely need to save it—calling an API or directly saving the information in a database. But all it has is unstructured natural language, coming from the conversation between the customer and the bot. A prompt to summarize and convert to structured data is needed:

[Click here to view code image](ch02_images.xhtml#f0046-01)

```
Return a json summary of the previous booking. Itemize the price for each item.
The json fields should be
1) name,
2) passport,
3) city,
4) room type with total price,
5) list of extras including total price,
6) arrival date,
7) departure date,
8) total days
9) total price of rooms and extras (calculated as the sum of the total room price and extra
price).
Return only the json, without introduction or final sentences.
Simulating a conversation with the HotelBot, a json like the following would be generated from
the previous prompt:
{"name":"Francesco Esposito","passport":"XXCONTOSO123","city":"Lisbon","room_type":{"single":15
0.00},"extras":{"parking":{"price_per_day":20.00,"total_price":40.00}},"arrival_date":"2023-06-
28","departure_date":"2023-06-30","total_days":2,"total_price":340.00}
```

##### Expanding

At some point, you might need to handle the inverse problem: generating a natural language summary from a structured JSON. The prompt to handle such a case could be something like:

[Click here to view code image](ch02_images.xhtml#f0047-01)

```
Return a text summary from the following json, using a friendly style. Write at most two
sentences.

{"name":"Francesco Esposito","passport":"XXCONTOSO123","city":"Lisbon","room_type":{"single":150.
00},"extras":{"parking":{"price_per_day":20.00,"total_price":40.00}},"arrival_date":"2023-06-28",
"departure_date":"2023-06-30","total_days":2,"total_price":340.00}
```

This would result in a reasonable output:

[Click here to view code image](ch02_images.xhtml#f0047-02)

```
Francesco Esposito will be staying in Lisbon from June 28th to June 30th. He has booked a single
room for $150.00 per night, and the total price including parking is $340.00 for 2 days.
```

#### Translating

Thanks to pretraining, one task that LLMs excel at is translating from a multitude of different languages—not just natural human languages, but also programming languages.

##### From natural language to SQL

One famous example taken directly from OpenAI references is the following prompt:

[Click here to view code image](ch02_images.xhtml#f0047-03)

```
### Postgres SQL tables, with their properties:
#
# Employee(id, name, department_id)
# Department(id, name, address)
# Salary_Payments(id, employee_id, amount, date)
#
### A query to list the names of the departments that employed more than 10 employees in the
last 3 months

SELECT
```

This prompt is a classic example of a plain completion (so, Completion API). The last part (`SELECT`) acts as cue, which is the jumpstart for the output.

In a broader sense, within the context of Chat Completion API, the system prompt could involve providing the database schema and asking the user which information to extract, which can then be translated into an SQL query. This type of prompt generates a query that the user should execute on the database only after assessing the risks. There are other tools to interact directly with the database through agents using the LangChain framework, discussed later in this book. These tools, of course, come with risks; they provide direct access to the data layer and should be evaluated on a case-by-case basis.

##### Universal translator

Let’s consider a messaging app in which each user selects their primary language. They write in that language, and if necessary, a middleware translates their messages into the language of the other user. At the end, each user will read and write using their own language.

The translator middleware could be a model instance with a similar prompt:

[Click here to view code image](ch02_images.xhtml#f0048-01)

```
Translate the following text from {user1Language} to {user2Language}:

<<<{message1}>>>
```

A full schema of the interactions would be:

1. User 1 selects its preferred language {user1Language}.
2. User 2 selects its preferred language {user2Language}.
3. One sends a message to the other. Let’s suppose User1 writes a message {message1} in {user1Language}.
4. The middleware translates {message1} in {user1Language} to {message1-translated} in {user2Language}.
5. User 2 sees {message1-translated} in its own language.
6. User 2 writes a message {message2} in {user2Language}.
7. The middleware performs the same job and sends the message to User1.
8. And so on….

### LLM limitations

So far, this chapter has focused on the positive aspects of LLMs. But LLMs have limitations in several areas:

- LLMs struggle with accurate source citations due to their lack of internet access and limited memory. Consequently, they may generate sources that appear reliable but are incorrect (this is called *hallucination*). Strategies like search-augmented LLMs can help address this issue.
- LLMs tend to produce biased responses, occasionally exhibiting sexist, racist, or homophobic language, even with safeguards in place. Care should be taken when using LLMs in consumer-facing applications and research to avoid biased results.
- LLMs often generate false information when faced with questions on which they have not been trained, confidently providing incorrect answers or hallucinating responses.
- Without additional prompting strategies, LLMs generally perform poorly in math, struggling with both simple and complex math problems.

It is important to be aware of these limitations. You should also be wary of prompt hacking, where users manipulate LLMs to generate desired content. All these security concerns are addressed later in this book.

### Summary

This chapter explored various basic aspects of prompt engineering in the context of LLMs. It covered common practices and alternative methods for altering output, including playing with hyperparameters. In addition, it discussed accessing OpenAI APIs and setting things up in C# and Python.

Next, the chapter delved into basic prompting techniques, including zero-shot and few-shot scenarios, iterative refining, chain-of-thought, time to think, and possible extensions. It also examined basic use cases such as booking chatbots for collecting information, summarization, and transformation, along with the concept of a universal translator.

Finally, the chapter discussed limitations of LLMs, including generating incorrect citations, producing biased responses, returning false information, and performing poorly in math.

Subsequent chapters focus on more advanced prompting techniques to take advantage of additional LLM capabilities and, later, third-party tools.
