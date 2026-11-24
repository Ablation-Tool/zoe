## Chapter 4

## Mastering language frameworks

In real life, most of the techniques explored in the previous chapter are not typically implemented from scratch, but rather are used through dedicated frameworks. The most commonly used frameworks are LangChain and Haystack, with Microsoft Semantic Kernel (SK) and Microsoft Guidance gaining ground. Additionally, LlamaIndex (or GPTIndex) is mostly used for the retrieval pipelines to ingest and query data. There are also low-code development platforms, like Microsoft Azure Machine Learning Prompt Flow, for streamlining the flow of prototyping, experimenting, iterating, and deploying LLM and AI applications.

This chapter covers the theory behind and practices for LangChain, Semantic Kernel (SK), and Guidance, emphasizing LangChain as the most stable among the three. The next part of the book provides real-world examples to show you how to use these frameworks.

![image](/api/v2/epubs/urn:orm:book:9780138280383/files/graphics/note.jpg) Note

This chapter focuses on textual interactions because, at the time of this writing, the latest models’ multimodal capabilities (such as GPT4-Visio) are not yet fully supported by the libraries discussed here. I anticipate a swift change in this situation, with interfaces likely being added to accommodate these capabilities. This expansion will reasonably involve extending the concept of `ChatMessages` to include a stream for input files. While all library interfaces have undergone significant changes in the past few months and will continue to do so, I don’t expect the fundamental concepts underlying them to change significantly.

### The need for an orchestrator

Dedicated frameworks serve as a higher-level API for LLMs and encompass an assortment of tools, components, and interfaces to streamline development. They act as orchestration tools for prompts, facilitating the interactive chaining of diverse actions, all rooted in prompts.

A driving factor behind the emergence of these frameworks has been the rapid evolution of LLMs—a trajectory that may soon lead to fundamental changes to models. In this context, the necessity for the abstraction provided by high-level frameworks becomes evident.

Another advantage of using a dedicated framework is that it enables you to employ different models for different tasks without having to learn the API syntax of each one. For example, you might want to use embeddings from Hugging Face’s models or some open-sourced local model because they’re cheaper, but OpenAI models for the chat itself. Either way, the programming interface remains the same.

Examples that underscore the relevance of frameworks like LangChain, SK, and Guidance include the following:

- Built-in vector stores connectors and the orchestration logic for retrieval augmented generation (RAG)
- Simplified memory management, allowing LLMs to track context from previous conversations
- Semi-autonomous agents for enhanced functionality
- Stricter control over the LLM output, ensuring a more precise and secure outcome
- A streamlined function-calling process

Each framework has its own specificity. LangChain is the pre-eminent open-source library for AI orchestration in Python and JavaScript, offering an alternative to options like C# and Python Semantic Kernel, as well as other options such as LlamaIndex. Conversely, Guidance is specialized in directing LLM outputs, refining the process of guiding LLMs during inference, and simplifying interaction to grant greater control over the final output.

![image](/api/v2/epubs/urn:orm:book:9780138280383/files/graphics/note.jpg) Note

OpenAI has launched the Assistants API, reminiscent of the concept of agents. Assistants can customize OpenAI models by providing specific instructions and accessing multiple tools concurrently, whether hosted by OpenAI or created by users. They autonomously manage message history and handle files in various formats, creating and referencing them in messages during tool use. However, the Assistants feature is designed to be low-code or no-code, with significant limitations in flexibility, making it less suitable or unsuitable for enterprise contexts.

#### Cross-framework concepts

Although each framework has its own specific nature, they are all, more or less, based on the same common abstractions. The concepts of prompt template, chain, external function (tools), and agent are present in all frameworks in different forms, as are the concepts of memory and logging.

##### Prompt templates, chains, skills, and agents

Prompt templates play a crucial role in organizing input prompts for LLMs. They can be likened to a string formatter (as in many programming languages), allowing data engineers to structure prompts in various ways to achieve a range of outcomes. For example, in question-answering scenarios, prompts can be customized to fit standard Q&A structures, present answers as bullet points, or even encapsulate issue overviews tied to the provided question, with few-shot examples. A prompt is essentially a compiled prompt template filled with variables, if any.

For instance, this is how a prompt template can be instantiated in LangChain:

[Click here to view code image](ch04_images.xhtml#f0081-01)

```
from langchain import PromptTemplate
prompt = PromptTemplate(
    input_variables=["product"],
    template="What is a good name for a company that makes {product}?",
)
```

While here, you can see an example of instantiating a prompt template in SK:

[Click here to view code image](ch04_images.xhtml#f0081-02)

```
var promptTemplate = new PromptTemplateConfig()
{
        Name = "Product",
        Description = "Product name generator",
        Template = @"What is a good name for a company that makes {{product}}?",
        TemplateFormat = "semantic-kernel",
        InputVariables = [
                new() { Name = "product", Description = "The product", IsRequired = true }
        ]
};
```

Chaining together different prompt templates, as well as simpler actions that don’t require an LLM to work (like removing spaces, fixing formatting, formatting the output, and so on), can technically be referred to as *building a chain.* Here is an example of a chain in LangChain, using LangChain Expression Language (LCEL):

[Click here to view code image](ch04_images.xhtml#f0081-03)

```
from langchain.chat_models import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

prompt = ChatPromptTemplate.from_template("tell me a short joke about {topic}")
model = ChatOpenAI()
output_parser = StrOutputParser()

chain = prompt | model | output_parser

chain.invoke({"topic": "ice cream"})
```

Sometimes you might need more than a static and predefined chain, which is essentially a sequence of LLM or other tool calls. Instead, you might require an indeterminate sequence contingent on user input. Within such chains, an *agent* (or *planner*) has access to an array of tools. User input determines which tool the agent chooses to invoke, if any.

![image](/api/v2/epubs/urn:orm:book:9780138280383/files/graphics/note.jpg) Note

Whereas chains use a preprogrammed sequence of actions embedded in code to execute actions, agents employ a language model as a cognitive engine to select what actions to take and when.

##### Memory

When adding memory to LLMs, there are two scenarios to consider: conversational memory (short-term memory) and context memory (long-term memory).

Conversational memory is what enables a chatbot to respond to multiple queries in a chat-like manner. It allows for a coherent conversation. Without it, every query would be treated as an entirely independent input, with no consideration of past interactions.

Short-term memory is not always “short-term” because it can be persisted to a database forever. However, at some point, a conversation can become too long for each new query and response to be sent to the LLM. The LLM context window is limited to, at most, 4k-16k-32k-128k tokens (depending on the model), and they have a cost. So, you basically have two options: sending only a limited window of messages between the user and the system (let’s say the last N messages) or summarizing the whole conversation through an LLM call or with more traditional information retrieval systems.

A memory system must facilitate two fundamental actions: retrieval and recording. Each chain establishes a fundamental execution logic that anticipates specific inputs. While certain inputs are directly provided by the user, others may originate from the memory system. During a single run, a chain engages with its memory system on two occasions:

- After receiving the first user input, but before executing the core logic, a chain will access its memory system to enhance the user inputs.
- After executing the core logic, but before presenting the answer, a chain will store the inputs and outputs of the ongoing run into memory. This enables future references in subsequent runs.

Semantic Kernel does not currently have a specific set of features to enable conversational memory, but developers are expected to use the long-term memory strategy with `VolatileMemoryStore` (not persisted) or a supported vector store (persisted). That is to say, short-term (conversational) memory should be handled as a collection of documents, in no specific order, to be queried with some similarity (usually cosine similarity) criteria based on the chosen memory provider. Another approach is to store the whole conversation in some non-relational database (usually MongoDB or CosmosDB) or in memory and reattach it every time.

LangChain, however, has a specific module for handling different types of conversational memories, such as the following:

- **ConversationBufferMemory** This is the simplest one; it just stores messages in a variable.
- **ConversationBufferWindowMemory** and **ConversationTokenBufferMemory** These keep a list of the interactions of the conversation over time, using only the last K interactions, based on the number of messages or the total number of tokens.
- **ConversationEntityMemory** This remembers facts about specific entities in a conversation. It extracts information on entities using an LLM and updates its knowledge about that entity over the interactions.
- **ConversationSummaryMemory** This summarizes the conversation and stores the summary in memory.
- **ConversationSummaryBufferMemory** This type of memory keeps recent interactions and summarizes the oldest, instead of completely flushing them.
- **VectorStoreRetrieverMemory** Like the SK approach, this stores the interactions as a document, without explicitly tracking the order of interactions.

##### Data retrievers

A *retriever* serves as an interface that provides documents based on an unstructured query. It possesses broader functionality than a vector store. Unlike a vector store, a retriever is not necessarily required to have the capability to store documents; its primary function is to retrieve and return them. Vector stores can serve as the foundational component of a retriever, but a retriever can also be built on top of a volatile memory or an old-style information retrieval system.

LangChain and SK support several data providers, available here:

- *[https://python.langchain.com/docs/integrations/retrievers/](https://python.langchain.com/docs/integrations/retrievers/)*
- *[https://github.com/microsoft/semantic-kernel/tree/main/dotnet/src/Connectors](https://github.com/microsoft/semantic-kernel/tree/main/dotnet/src/Connectors)*

Following is a sample code snippet to add some dumb documents to a `VolatileMemoryStore` and query them with SK:

[Click here to view code image](ch04_images.xhtml#f0083-01)

```
var kernel = Kernel.CreateBuilder()
            .AddAzureOpenAIChatCompletion(deploymentName: AOAI_DEPLOYMENTID, endpoint: AOAI_ENDPOINT, apiKey:
                        AOAI_KEY)
            .AddAzureOpenAITextEmbeddingGeneration(deploymentName: AOAI_EMBEDDING, endpoint: AOAI_ENDPOINT, apiKey:
                        AOAI_KEY)
            .Build();
// Create an embedding generator to use for semantic memory.
var embeddingGenerator = new OpenAITextEmbeddingGenerationService(TestConfiguration.OpenAI.EmbeddingModelId,
            TestConfiguration.OpenAI.ApiKey);
SemanticTextMemory textMemory = new(memoryStore, embeddingGenerator);
await textMemory.SaveInformationAsync(MemoryCollectionName, id: "info1", text: "My name is Francesco");

//Querying
await foreach (var answer in textMemory.SearchAsync(
            collection: MemoryCollectionName,
            query: "What's my name?",
            limit: 2,
            minRelevanceScore: 0.75,
            withEmbeddings: true,
{
            Console.WriteLine($"Answer: {answer.Metadata.Text}");
}
```

Note that with SK, documents are always embedded before being stored (while with LangChain this is not always the case), but the lookup can also be based on a specific key.

##### Logging and tracing

In real-world scenarios, several LLM calls are made with concatenated and well-formatted prompts for each interaction between the user and the system. This makes it quite difficult to track down the exact run chain to analyze prompts and token consumption.

Only OpenAI models support token consumption tracking. For LangChain, this can be achieved in the following way:

[Click here to view code image](ch04_images.xhtml#f0084-01)

```
from langchain.agents import load_tools
from langchain.agents import initialize_agent
from langchain.agents import AgentType
from langchain.llms import OpenAI

llm = OpenAI(temperature=0)
tools = load_tools(["serpapi", "llm-math"], llm=llm)
agent = initialize_agent(
    tools, llm, agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION, verbose=True
)
with get_openai_callback() as cb:
       response = agent.run("Who is Olivia Wilde's boyfriend? What is his current age raised to
the 0.23 power?")
       print(f"Total Tokens: {cb.total_tokens}")
       print(f"Prompt Tokens: {cb.prompt_tokens}")
       print(f"Completion Tokens: {cb.completion_tokens}")
       print(f"Total Cost (USD): ${cb.total_cost}")
```

The key points in the code are `verbose=True` and the callback function, which expose certain token-usage metrics.

The verbosity option enables the logging of each intermediate step. It is available on top of the agent module or on the chain module in the following way:

[Click here to view code image](ch04_images.xhtml#f0084-02)

```
conversation = ConversationChain(
    llm=chat,
    memory=ConversationBufferMemory(),
    verbose=True
)
conversation.run("What is ChatGPT?")
```

SK exposes roughly the same information available when logging is enabled:

[Click here to view code image](ch04_images.xhtml#f0084-03)

```
IKernelBuilder builder = Kernel.CreateBuilder();
builder.AddAzureOpenAIChatCompletion(***CONFIG HERE***);
builder.Services.AddLogging(c => c.AddConsole().SetMinimumLevel(LogLevel.Information));
Kernel kernel = builder.Build();
```

Also, installing SK Extension on Visual Studio Code can help with testing functions without any code and with inspecting the token usage for those functions.

Planners (equivalent to LangChain agents), which are covered in a dedicated section later in this chapter, can also be logged and monitored.

SK incorporates telemetry through logging, metering, and tracing, and native .NET instrumentation tools are employed to instrument the code. This provides flexibility to use various monitoring platforms such as Application Insights, Prometheus, Grafana, and more. You can enable tracing in the following way:

[Click here to view code image](ch04_images.xhtml#f0085-01)

```
using System.Diagnostics;
var activityListener = new ActivityListener();
activityListener.ShouldListenTo =
       activitySource => activitySource.Name.StartsWith("Microsoft.SemanticKernel",
StringComparison.Ordinal);
ActivitySource.AddActivityListener(activityListener);
```

Metering with a telemetry client instance like Application Insights can be applied with these lines of code:

[Click here to view code image](ch04_images.xhtml#f0085-02)

```
using System.Diagnostics.Metrics;
var meterListener = new MeterListener();
meterListener.InstrumentPublished = (instrument, listener) =>
{
       if (instrument.Meter.Name.StartsWith("Microsoft.SemanticKernel", StringComparison.
Ordinal)
       {
              listener.EnableMeasurementEvents(instrument);
        }
};
meterListener.SetMeasurementEventCallback<double>((instrument, measurement, tags, state) =>
{
       telemetryClient.GetMetric(instrument.Name).TrackValue(measurement);
});
meterListener.Start();
```

In both cases, you can select specific metrics or activity, with a more restrictive condition on the namespace string.

With LangChain, you can enable full tracing capabilities not only for agents, but also taking a more complex approach: using a web server to gather data about agent runs. The web server uses port 8000 to accumulate trace details, while port 4173 is allocated for hosting the user interface. The web server operates within a Docker container. So, in addition to setting up LangChain, Docker must be set up, with an executable `docker-compose` command.

Running the following command in the terminal in the correct Python environment starts the server container:

```
-m langchain.server
```

The following lines of code enable tracing with a specified session:

[Click here to view code image](ch04_images.xhtml#f0085-03)

```
from langchain.llms import AzureOpenAI
from langchain.callbacks import tracing_enabled
with tracing_enabled('session_test') as session:
        assert session
        llm = AzureOpenAI(deployment_name=deployment_name)
        llm("Tell me a joke")
```

You can then navigate the web application at *[http://localhost:4173/sessions](http://localhost:4173/sessions)* to select the correct session. (See [Figure 4-1](ch04.xhtml#ch04fig01).)

![The figure is a screenshot from a localhost that contains the list of traced messages for a session named "session_test".](/api/v2/epubs/urn:orm:book:9780138280383/files/graphics/04fig01.jpg)

***Figure 4-1** LangChain tracing server.*

![image](/api/v2/epubs/urn:orm:book:9780138280383/files/graphics/note.jpg) Note

LangSmith, an additional web platform cloud-hosted by LangChain, could be a more reliable option for production applications, but it needs a separate setup on [smith.langchain.com](http://smith.langchain.com). More on this in [Chapter 5](ch05.xhtml#ch05).

#### Points to consider

These frameworks simplify some well-known patterns and use cases and provide various helpers. But as usual, you must carefully consider whether to use them on a case-by-case basis, based on the complexity and specificity of the project at hand. This is especially true regarding the development environment, the desired reusability, the need to modify and debug each individual prompt, and the associated costs.

##### Different environments

LangChain is available in Python and JavaScript; SK is available in C#, Java, and Python; and Guidance is available in Python. In a general sense, Python offers a broader range of NLP tools than .NET, but .NET (or Java) might provide more enterprise-oriented features, which may be equally essential.

The technological choice is not straightforward, just as it’s not clear whether to use a single technology stack or integrate multiple ones using APIs. When the use case becomes more complex with interactions that involve not just the user and the LLM but also databases, caching, login, old-style UI, and so on, a practical approach is often to isolate LLM layers within some shared scope into components. These components can even be separate web applications communicating through APIs. This approach offers the advantage of isolation along with the ability to monitor costs and performance separately. Of course, it also comes with a bit more latency and requires abstraction work to build the API layer.

![image](/api/v2/epubs/urn:orm:book:9780138280383/files/graphics/tip.jpg) Tip

In these turbulent times, it sometimes makes sense to choose based on a specific feature, perhaps available only on a specific tech stack (usually Python).

##### Costs, latency, and caching

One aspect to consider when deciding whether and which frameworks to use is the cost—both in terms of the cost of calls and the cost of latency applied to underlying models (especially paid ones from OpenAI). For instance, agents and planners consume many tokens and therefore incur significant costs by going back and forth with partial prompts and responses, as seen in patterns like ReAct (discussed shortly).

Certain functions, like the previously discussed `ConversationSummaryMemory` function, are extremely useful and powerful, but require multiple calls to LLMs, potentially becoming much more expensive when scaling up the number of users.

Another example, within the context of RAG, could involve rephrasing user questions to optimize them to obtain more relevant document chunks and to enable the LLM to provide better responses. A more cost-effective solution, however, applied upstream when the embedding database is generated, could involve having an LLM rephrase the document chunk—specifically asking it to reword it under the assumption that a user might inquire about it (perhaps providing a few-shot example).

One approach for reducing general latency that can be explored further is caching LLM results. LangChain natively supports this via its llm_cache (through SQLite). Caching can also be used via the GPTCache library and must be re-implemented manually in SK. For its part, Guidance has its own optimization flow (called *acceleration*) for local models only.

##### Reusability and poor debugging

One pivotal challenge lies in the reusability of prompts and orchestrated actions. Despite the allure of creating reusable templates, most of the time we use GPT-4 and GPT-3.5 turbo exclusively. The notable exception is in the embedding phase, in which open-sourced models can perform well and can sometimes be refined and fine-tuned to perform even better.

Each feature and step within a chain necessitates custom prompts and meticulous tuning to generate desired outputs. Consequently, seamless reusability remains elusive, somewhat limiting the abstraction attempts of frameworks like LangChain and SK. They also sometimes promote tool lock-in for minimal benefit.

Leveraging external platforms such as LangSmith, PromptFlow, or HumanLoop proves advantageous not only for experimentation but also for comprehensive monitoring and debugging of all essential steps in a production solution. In fact, another noteworthy concern revolves around debugging and customization. While these frameworks offer a structured approach to orchestration, debugging errors within the chain can prove arduous, even with verbose logging. Moreover, venturing beyond the confines of documented workflows quickly leads to intricate challenges that demand a deep dive into the frameworks’ codebases.

These frameworks aim to streamline interactions, and they are great with standard (but still various) use cases. For instance, a standard RAG app can be executed in minutes using LangChain or SK instead of days when writing it from scratch. But when dealing with more complex scenarios, or when adding complexity (like testing), compatibility and adaptability remain areas of exploration and refinement.

### LangChain

LangChain is a versatile framework that empowers applications to interact with data sources and their environment. This framework offers two core features:

- **Components** LangChain provides modular abstractions for language model interactions, offering a collection of implementations for each abstraction. These components are highly adaptable and user-friendly, whether used as part of the LangChain framework or independently.
- **Off-the-shelf chains** LangChain includes predesigned sequences of components for specific high-level tasks.

These ready-made chains streamline initial development. For more intricate applications, the component-based approach allows for the customization of existing chains or the creation of new ones.

The framework supports various modules:

- **Model I/O** This is a base interface with different language models.
- **Data connection** This is an interface with application-specific data and long-term memory.
- **Chains** These handle chains of LLM calls.
- **Agents** These are dynamic chains that can choose, based on a reasoning LLM, which tools and API to use given high-level instructions.
- **Memory** Short-term memory persists between runs of a chain.
- **Callbacks** These log the intermediate steps of any interaction with an LLM.

Whether LangChain can be used in production and enterprise contexts depends on various considerations. On one hand, there aren’t many alternatives beyond implementing some pieces using the base OpenAI APIs or Hugging Face for the models you want to use. On the other hand, LangChain is still immature in terms of framework architecture, with various ways of achieving the same thing and limited documentation at the time of this writing.

#### Models, prompt templates, and chains

Prompts are the most crucial aspect in an application that incorporates LLMs. Series of prompt templates has become almost standard. Each of these serves a distinct purpose, such as classification, generation, question-answering, summarization, and translation. LangChain incorporates all these standard prompts and offers a user-friendly interface for crafting and tailoring new prompt templates.

Chosen models are also crucial, and the chains of calls to these models must be correctly managed. LangChain helps to seamlessly integrate all these components into a unified application flow. For instance, a chain could be designed to receive user input, apply a prompt template for formatting, further process the formatted response through an LLM, and finally pass the output through a parser before delivering the result back to the user.

##### Models

LangChain was born with the goal of abstracting itself from the APIs of each individual model. LangChain supports many models, including Anthropic models like Claude2, models from OpenAI and Azure OpenAI (which you will use in the examples), Llama2 via LlamaAPI models, Hugging Face models (both in the local version and the one hosted on the Hugging Face Hub), Vertex AI PaLM models, and Azure Machine Learning models.

![image](/api/v2/epubs/urn:orm:book:9780138280383/files/graphics/note.jpg) Note

Azure Machine Learning is the Azure platform for building, training, and deploying ML models. These models can be selected from the Azure Model Catalog, which includes OpenAI Foundation Models (which can be fine-tuned if needed) and Azure Foundation Models (such as those from Hugging Face and open-source models like Llama2).

One key aspect is the difference between text completion and chat completion API calls. Chat models and normal text completion models, while subtly related, possess distinct characteristics that influence their usage within LangChain. LLMs in LangChain primarily refer to pure text-completion models, interacting through APIs that accept a string prompt as input and generate a string completion as output. OpenAI’s GPT-3 is an example of an LLM. In contrast, chat models like GPT-4 and Anthropic’s Claude are designed specifically for conversations. Their APIs exhibit a different structure, accepting a list of chat messages, each labeled with the speaker (for example, `System`, `AI`, or `Human`), and producing a chat message as output.

LangChain aims to enable interchangeability between these models by implementing the Base Language Model interface, with methods like `predict` for LLMs and `predict messages` for chat models available for both. It also uses an internal converter, which basically transforms a text-completion call into a chat-message call, appending the text into a human message and vice versa, and appending all the messages into a plain text completion call.

The introduction of chat models was motivated by the need for structured user input, potentially enhancing the model’s ability to follow predefined objectives—vital for building safer applications. Based on personal experience, chat models perform better almost every time.

![image](/api/v2/epubs/urn:orm:book:9780138280383/files/graphics/note.jpg) Note

When working with Azure OpenAI, it is advisable to set environment variables for the endpoint and API key rather than passing them each time to the model. To achieve this, you need to configure the following environment variables: `OPENAI_API_TYPE` (set to `azure`), `AZURE_OPENAI_ENDPOINT`, and `AZURE_OPENAI_KEY`. On the other hand, if you are interfacing directly with OpenAI models, you should set `OPENAI_ENDPOINT` and `OPENAI_KEY`.

##### Prompt templates

LLM applications do not directly feed user input into the model. Instead, they employ a more comprehensive text segment: the prompt template.

Starting with a base completion prompt, the code is as follows:

[Click here to view code image](ch04_images.xhtml#f0090-01)

```
from langchain.prompts import PromptTemplate
prompt = PromptTemplate(
    input_variables=["product"],
    template="What is a good name for a company that makes {product}?"
)
print(prompt.format(product="data analysis in healthcare"))
```

As highlighted, LangChain aims to simplify the process of transitioning between competitive and chat-based approaches. However, for real-world scenarios, a chat prompt can be more suitable and can be instantiated in the following way:

[Click here to view code image](ch04_images.xhtml#f0090-02)

```
from langchain.prompts import ChatPromptTemplate, SystemMessagePromptTemplate,
HumanMessagePromptTemplate
human_message_prompt = HumanMessagePromptTemplate(
        prompt=PromptTemplate(
            template="What is a good name for {company} that makes {product}?",
            input_variables=["company", "product"],
        )
    )
chat_prompt_template = ChatPromptTemplate.from_messages([human_message_prompt])
print(chat_prompt_template.format_prompt(company="AI Startup", product="data analysis in
healthcare"))
```

At some point, you might need to use the few-shot prompting technique. There are three ways to format such a prompt: by explicitly writing it, by formatting it based on an example set, and by having the framework select the relevant examples from an `ExampleSelector` instance.

To dynamically select the examples, you must deal with the existing `ExampleSelector` or create a new one by implementing the `BaseExampleSelector` interface. The existing selectors are as follows:

- **SemanticSimilarityExampleSelector** This finds the most similar example based on the embeddings of the examples and the input, so it needs a vector store and an `EmbeddingModel` (meaning additional infrastructure and costs are involved).
- **MaxMarginalRelevanceExampleSelector** This works like the `SemanticSimilarityExampleSelector` (so it needs vector stores and embeddings), but it also privileges diversity.
- **NGramOverlapExampleSelector** This selects examples based on a different (and less effective) similarity measure that doesn’t need any embedding: ngram overlap score.
- **LengthBasedExampleSelector** This selects examples based on a max-length parameter, so it changes the number of selected samples to reflect it.

Having a selector in place, the code to build the few-shot prompt would look like this:

[Click here to view code image](ch04_images.xhtml#f0091-01)

```
few_shot_prompt = FewShotChatMessagePromptTemplate(
    input_variables=["input"],
    example_selector=example_selector,
    # Each example will become 2 messages: 1 human, and 1 AI
    example_prompt=ChatPromptTemplate.from_messages(
        [("human", "{input}"), ("ai", "{output}")]
    ),
)
```

![image](/api/v2/epubs/urn:orm:book:9780138280383/files/graphics/note.jpg) Note

The `ExampleSelector` selects examples based on the input, so an input variable must be defined in this case.

##### Chains

Chains allow you to combine multiple components to create a single, coherent application.

There are two primary ways to chain different calls. The traditional (legacy) method involves using the Chain interface, while the latest approach involves employing the LangChain Expression Language (LCEL).

From the Chain interface, LangChain offers several foundational chains:

- **LLMChain** This comprises a prompt template and a language model, which can be either an LLM or a chat model. The process involves shaping the prompt template with supplied input key values (and memory if accessible), forwarding the modified string to the chosen model, and obtaining the model’s output.
- **RouterChain** This creates a chain that dynamically selects the next chain to use based on a given input. It is made up of the `RouterChain` itself and the destination chains.
- **SequentialChain** This bridges multiple chains. There are two types of sequential chains:
  - **SimpleSequentialChain** With this type of sequential chain, each step has a singular input/output (the output of one step is the input to the next).
  - **TransformChain** This preprocesses the input—for example, removing extra spaces, obtaining only the first N characters, replacing some words, or whatever other transformation you may want to apply to the input. Note that this type of chain usually needs only code, not an LLM.

![image](/api/v2/epubs/urn:orm:book:9780138280383/files/graphics/note.jpg) Note

You can also build a custom chain by subclassing a foundational chain class.

Built on top of these foundational chains are several well-tested common-use chains, available here: *[https://github.com/langchain-ai/langchain/tree/master/libs/langchain/langchain/chains](https://github.com/langchain-ai/langchain/tree/master/libs/langchain/langchain/chains)*. The most popular are `ConversationChain`, `AnalyzeDocumentChain`, `RetrievalQAChain`, and `SummarizeChain`, but chains for QA generation (to build questions/answers for a given document) and math are also common. One math chain, `PALChain`, uses Python REPL (Read-Eval-Print Loop) to compile and execute generated code from the model(s).

Let’s start exploring the code with a base chain with the legacy Chain interface, on a chat model:

[Click here to view code image](ch04_images.xhtml#f0092-01)

```
human_message_prompt = HumanMessagePromptTemplate(
        prompt=PromptTemplate(
            template="What is a good name for {company} that makes {product}?",
            input_variables=["company", "product"],
        )
    )
chat_prompt_template = ChatPromptTemplate.from_messages([human_message_prompt])
chat = ChatOpenAI(temperature=0.9) #as it's a creative task, let's keep a high temperature
chain = LLMChain(llm=chat, prompt=chat_prompt_template)
print(chain.run(
        {
                'company': "AI Startup", 'product': "healthcare bot-assistant"
        }
))
```

The following example explains well the logic behind LCEL:

[Click here to view code image](ch04_images.xhtml#f0092-02)

```
from langchain.chat_models import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

prompt = ChatPromptTemplate.from_template("tell me a short joke about {topic}")
model = ChatOpenAI()
output_parser = StrOutputParser()

chain = prompt | model | output_parser

chain.invoke({"topic": "ice cream"})
```

![image](/api/v2/epubs/urn:orm:book:9780138280383/files/graphics/note.jpg) Note

`StrOutputParser` simply converts the output of the chain (that is of a `BaseMessage` type, as it’s a `ChatModel`) to a string.

We could certainly delve into more intricate chains that encompass multiple inputs and result in multiple distinct outputs, with inner parallel steps. These would be unlike the previous example that featured a straightforward pattern of accepting a single string as input and delivering a single string as output. The nomenclature of input and output variable names becomes crucial in this context, as shown in the following code:

[Click here to view code image](ch04_images.xhtml#f0092-03)

```
from langchain.prompts import PromptTemplate
from langchain.schema import StrOutputParser
from langchain_core.runnables import RunnablePassthrough
from langchain.chat_models import AzureChatOpenAI

productNamePrompt = PromptTemplate(
    input_variables=["product"],
    template="What is a good name for a company that makes {product}?",
)
productDescriptionPrompt = PromptTemplate(
    input_variables=["productName"],
    template="What is a good description for a product called {productName} for {product}? ",
)

runnable = (
    {"productName": productNamePrompt | llm | StrOutputParser(), "product":
RunnablePassthrough()}
    | productDescriptionPrompt
    | AzureChatOpenAI(azure_deployment=deployment_name)
    | StrOutputParser()
)
runnable.invoke({"product": "bot for airline company"})
```

In this example, the first piece (an LLM being invoked with a prompt and returning an output) uses the variable `("bot for airline company")` to produce a product name. This is then passed, together with the initial input, to the second prompt, which creates the product description. This produces the following results:

[Click here to view code image](ch04_images.xhtml#f0093-01)

```
AirBot Solutions is an innovative and efficient bot designed specifically for airline companies.
This advanced product utilizes cutting-edge technology to streamline and enhance various aspects
of airline operations. With AirBot Solutions, airline companies can automate and improve
customer service, reservations, flight management, and more. This intelligent bot is capable
of handling a wide range of tasks, including answering customer inquiries, providing real-time
flight updates, assisting with bookings, and offering personalized recommendations.
```

##### Memory

You can add memory to chains in a couple of different ways. One is to use the `SimpleMemory` interface to add specific memories to the chain, like so:

[Click here to view code image](ch04_images.xhtml#f0093-02)

```
conversation = ConversationChain(
    llm=chat,
    verbose=True,
    memory=SimpleMemory(memories={"name": "Francesco Esposito", "location": "Rome"}),
)
```

The other is through conversational memory, as described earlier in this chapter:

[Click here to view code image](ch04_images.xhtml#f0093-03)

```
conversation = ConversationChain(
    llm=chat,
    verbose=True,
    memory=ConversationBufferMemory()
)
```

![image](/api/v2/epubs/urn:orm:book:9780138280383/files/graphics/note.jpg) Note

Of course, you can use all the memory types described earlier, not only `ConversationBufferMemory`.

It is also possible to use multiple memory classes in the same chain—for instance, `ConversationSummaryMemory` (which uses an LLM to produce a summary) and a normal `ConversationBufferMemory`. To combine multiple memories, you use `CombinedMemory`:

[Click here to view code image](ch04_images.xhtml#f0094-01)

```
conv_memory = ConversationBufferMemory(
    memory_key="chat_history_lines", input_key="input"
)

summary_memory = ConversationSummaryMemory(llm=OpenAI(), input_key="input")
# Combined
memory = CombinedMemory(memories=[conv_memory, summary_memory])
```

![image](/api/v2/epubs/urn:orm:book:9780138280383/files/graphics/note.jpg) Note

Of course, you must inject the respective `memory_key` into the (custom) prompt message.

With LCEL, the memory can be injected in the following way:

[Click here to view code image](ch04_images.xhtml#f0094-02)

```
prompt = ChatPromptTemplate.from_messages(
    [
        ("system", "You're an assistant who's good at solving math problems."),
        MessagesPlaceholder(variable_name="history"),
        ("human", "{question}"),
    ]
)chain = (
    RunnablePassthrough.assign(
        history=RunnableLambda(memory.load_memory_variables) | itemgetter("history")
    )
    | prompt
    | llm
)
```

In this case, the `question` input is the user input message, while the `history` key contains the historical chat messages.

![image](/api/v2/epubs/urn:orm:book:9780138280383/files/graphics/note.jpg) Note

At the moment, memory is not updated automatically through the conversation. You can do so manually by calling `add_user_message` and `add_ai_message` or via `save_context`.

##### Parsing output

Sometimes you need structured output from an LLM, and you need some way to force the model to produce it. To achieve this, LangChain implements `OutputParser`. You can also build your own implementations with three core methods:

- **get_format_instructions** This method returns a string with directions on how the language model’s output should be structured.
- **parse** This method accepts a string (the LLM’s response) and processes it into a particular structure.
- **parse_with_prompt (optional)** This method accepts both a string (the language model’s response) and a prompt (the input that generated the response) and processes the content into a specific structure. Including this prompt aids the `OutputParser` in potential output adjustments or corrections, using prompt-related information for such refinements.

The main parsers are `StrOutputParser`, `CommaSeparatedListOutputParser`, `DatetimeOutputParser`, `EnumOutputParser`, and the most powerful `Pydantic` (JSON) parser. The code for a simple `CommaSeparatedListOutputParser` would look like the following:

[Click here to view code image](ch04_images.xhtml#f0095-01)

```
from langchain.output_parsers import CommaSeparatedListOutputParser
output_parser = CommaSeparatedListOutputParser()

format_instructions = output_parser.get_format_instructions()
prompt = PromptTemplate(
            input_variables=["company", "product"],
            template="Generate 5 product names for {company} that makes
{product}?\n{format_instructions}",
            partial_variables={"format_instructions": format_instructions})

_input = prompt.format(company="AI Startup", product="HealthCare bot")
chat = AzureOpenAI(temperature=.7, deployment_name=deployment_name)
output = chat(_input)
output_parser.parse(output)
```

![image](/api/v2/epubs/urn:orm:book:9780138280383/files/graphics/note.jpg) Note

Not all parsers work with ChatModels.

##### Callbacks

LangChain features a built-in callbacks system that facilitates integration with different phases of the LLM application, which is valuable for logging, monitoring, and streaming. To engage with these events, you can use the `callbacks` parameter present across the APIs. You can use a few built-in handlers or implement a new one from scratch.

Here are the methods that a `CallbackHandler` interface must implement:

- **on_llm_start** Run when the LLM starts running.
- **on_chat_model_start** Run when the chat model starts running.
- **on_llm_new_token** Run on a new LLM token. This is only available when streaming (discussed later) is enabled.
- **on_llm_end** Run when the LLM stops running.
- **on_llm_error** Run when the LLM experiences an error.
- **on_chain_start** Run when a chain starts running.
- **on_chain_end** Run when a chain stops running.
- **on_chain_error** Run when a chain experiences an error.
- **on_tool_start** Run when a tool starts running.
- **on_tool_end** Run when a tool stops running.
- **on_tool_error** Run when a tool experiences an error.
- **on_text** Run on arbitrary text.
- **on_agent_action** Run on agent action.
- **on_agent_finish** Run when agent finishes.

The most basic handler is `StdOutCallbackHandler`, which logs all events to `stdout`, achieving the same results as `Verbose=True`:

[Click here to view code image](ch04_images.xhtml#f0096-01)

```
handler = StdOutCallbackHandler()
chain = LLMChain(llm=chat, prompt=chat_prompt_template,callbacks=[handler])
chain.run({'company': "AI Startup", 'product': "healthcare bot-assistant"})
```

Or, equivalently, passing the callback in the run method:

[Click here to view code image](ch04_images.xhtml#f0096-02)

```
chain = LLMChain(llm=chat, prompt=chat_prompt_template)
chain.run({'company': "AI Startup", 'product': "healthcare bot-assistant"}, callbacks=[handler])
```

![image](/api/v2/epubs/urn:orm:book:9780138280383/files/graphics/note.jpg) Note

Agents, as you will soon see, expose similar parameters.

#### Agents

In LangChain, an agent serves as a crucial mediator, enhancing tasks beyond what the LLM API alone can achieve due to its inability to access data in real time. Acting as a bridge between the LLM and tools like Google Search and weather APIs, the agent makes decisions based on prompts, leveraging the LLM’s natural language understanding. Unlike traditional hard-coded action sequences, the agent’s actions are determined by recursive calls to the LLM, with implications in terms of cost and latency.

Empowered by the language model and a personalized prompt, the agent’s responsibility includes decision-making. LangChain offers various customizable agent types, with tools as callable functions. Effectively configuring an agent to access certain tools, and describing these tools, are vital for the agent’s successful operation.

LangChain provides a variety of customizable tools and supports the creation of new ones. Toolkits, introduced to group tools for specific objectives, function as plug-ins. You can explore available toolkits here: *[https://python.langchain.com/docs/integrations/toolkits/](https://python.langchain.com/docs/integrations/toolkits/)*.

Reporting and BI purposes are common use cases for the SQL Agent, which uses the SQLDatabaseToolkit. In critical scenarios, it’s crucial to limit the agent’s permissions and restrict the database user’s access.

##### Agent types

LangChain supports the following agents, usually available in text-completion or chat-completion mode:

- **Zero-shot ReAct** This agent employs the ReAct framework to decide which tool to use based solely on the tool’s description. It supports multiple tools, with each tool requiring a corresponding description. This is currently the most versatile, general-purpose agent.
- **Structured input ReAct** This agent is capable of using multi-input tools. Unlike older agents that specify a single string for action input, this agent uses a tool’s argument schema to create a structured action input. This is especially useful for complex tool usage, such as precise navigation within a browser.
- **OpenAI Functions** This agent is tailored to work with specific OpenAI models, like GPT-3.5-turbo and GPT-4, which are fine-tuned to detect function calls and provide corresponding inputs.
- **Conversational** This agent, which has a helpful and conversational prompt style, is designed for conversational interactions. It uses the ReAct framework to select tools and employs memory to retain previous conversation interactions.
- **Self ask with search** This agent relies on a single tool, Intermediate Answer, which is capable of searching and providing factual answers to questions. This agent uses tools like a Google search API.
- **ReAct document store** This agent leverages the ReAct framework to interact with a document store. It requires two specific tools: a search tool for document retrieval and a lookup tool to find terms in the most recently retrieved document. This agent is reminiscent of the original ReAct paper.
- **Plan-and-execute agents** These follow a two-step approach (with two LLMs) to achieve objectives. First, they plan the necessary actions. Next, they execute these subtasks. This concept draws inspiration from BabyAGI and the “Plan-and-Solve” paper (*[https://arxiv.org/pdf/2305.04091.pdf](https://arxiv.org/pdf/2305.04091.pdf)*).

##### ReAct Framework

ReAct, short for Reasoning and Acting, has revolutionized LLMs by merging reasoning (akin to chain-of-thought) and acting (similar to function calling) to enhance both performance and interpretability. Unlike traditional methods for achieving artificial general intelligence (AGI), which often involve reinforcement learning, ReAct aims to generalize across problems using a distinctive approach.

The fundamental concept behind ReAct is to emulate human task execution. Similar to the way humans plan steps, adapt for exceptions, and seek external information, ReAct adopts an interleaved approach of reasoning and acting. Its success lies in seamlessly integrating reasoning (reason to act) with interactions (act to reason), achieved through few-shot prompting and function calling.

To facilitate reasoning prompts, ReAct uses a designed action space with three actions: `search[entity]`, `lookup[string]`, and `finish[answer]`. These mimic how humans interact with information sources to enhance the synthesis of reasoning and action, simulating human-like interaction and decision-making. Prompting involves decomposed thoughts, Wikipedia observations, common sense, arithmetic reasoning, and search reformulation, guiding the chain of actions.

The comparative results between different reasoning approaches for LLMs are the following, taken from the original paper, “Synergizing Reasoning and Acting in Language Models” by Yao et al., available here: *[https://arxiv.org/pdf/2210.03629.pdf](https://arxiv.org/pdf/2210.03629.pdf)*.

**QUESTION**

*Seven Brief Lessons on Physics was written by an Italian physicist that has worked in France since what year?*

**STANDARD APPROACH**

***Answer:*** *1986*

**REASON ONLY APPROACH**

***Thought:*** Let’s think step by step. Seven Brief Lessons on Physics was written by Carlo Rovelli. Carlo Rovelli has worked in France since 1990.

***Answer:*** 1990

**ACT ONLY APPROACH**

***Act 1:*** Search [Seven Brief Lessons on Physics]

***Obs 1:*** Seven Brief Lessons on Physics (Italian: Sette brevi lezioni di fisica) is a short book by the Italian physicist Carlo Rovelli. Originally published in Italian in...

***Act 2:*** Look up [Carlo Rovelli]

***Obs 2:*** (Result 11) Seven Brief Lessons on Physics (Italian: Sette brevi lezioni di fisica) is a short book by the Italian physicist Carlo Rovelli.

***Act 3:*** *Finish [1983]*

**REACT APPROACH**

***Thought 1:*** I need to search Seven Brief Lessons on Physics, find its author, then find when the author has worked in France since.

***Act 1:*** Search [Seven Brief Lessons on Physics]

***Obs 1:*** Seven Brief Lessons on Physics (Italian: Sette brevi lezioni di fisica) is a short book by the Italian physicist Carlo Rovelli. Originally published in Italian in....

***Thought 2:*** The author of Seven Brief Lessons on Physics is Carlo Rovelli. I need to search Carlo Rovelli next and find when he has worked in France since.

***Act 2:*** Search [Carlo Rovelli]

***Obs 2:*** Carlo Rovelli is an Italian theoretical physicist and writer who has worked in Italy, the United States and, since 2000, in France. [1] He is also currently a Distinguished Visiting Research Chair at the Perimeter Institute...

***Thought 3:*** Carlo Rovelli has worked in France since 2000. So the answer is 2000.

***Act 3:*** *Finish [2000]*

In LangChain, the base ReAct prompt used for zero-shot agents (agents without memory) looks like this:

[Click here to view code image](ch04_images.xhtml#f0099-01)

```
Answer the following questions as best you can. You have access to the following tools:
{tools}
Use the following format:
Question: the input question you must answer
Thought: you should always think about what to do
Action: the action to take, should be one of [{tools}]
Action Input: the input to the action
Observation: the result of the action
... (this Thought/Action/Action Input/Observation can repeat N times)
Thought: I now know the final answer
Final Answer: the final answer to the original input question
Begin!
Question: {input}
Thought:{agent_scratchpad}
```

![image](/api/v2/epubs/urn:orm:book:9780138280383/files/graphics/note.jpg) Note

This code requires the use of `agent_scratchpad` because this is where the agent adds its intermediate steps (recursively calling the LLM and tools). `agent_scratchpad` serves as a repository for recording each thought or action executed by the agent. This ensures that all thoughts and actions within the ongoing agent executor chain remain accessible for the subsequent thought-action-observation loop, thereby maintaining continuity in agent actions.

##### Usage

Let’s start building a working sample for an agent with access to Google Search and a few custom tools. First, define the tools:

[Click here to view code image](ch04_images.xhtml#f0099-02)

```
from langchain.tools import Tool, tool
#To use GoogleSearch, you must run -m pip install google-api-python-client
from langchain.utilities import GoogleSearchAPIWrapper
from langchain.agents import AgentType, initialize_agent
from langchain.chat_models import AzureChatOpenAI
from langchain.prompts.chat import (PromptTemplate, ChatPromptTemplate,
HumanMessagePromptTemplate)
from langchain.chains import LLMChain
import os
os.environ["GOOGLE_CSE_ID"] = "###YOUR GOOGLE CSE ID HERE###"
#More on: https://programmablesearchengine.google.com/controlpanel/create
os.environ["GOOGLE_API_KEY"] = "###YOUR GOOGLE API KEY HERE###"
#More on: https://console.cloud.google.com/apis/credentials

search = GoogleSearchAPIWrapper()

#one way to define a tool
@tool
def get_word_length(word: str) -> int:
    """Returns the length, in terms of characters, of a string."""
    return len(word)

@tool
def get_number_words(str: str) -> int:
    """Returns the number of words of a string."""
    return len(str.split())

#another way to set up a tool
def top3_results(query):
    "Search Google for relevant and recent results."
    return search.results(query, 3)

get_top3_results = Tool(
    name="GoogleSearch",
    description="Search Google for relevant and recent results.",
    func=top3_results
)
```

You can also set up a chain (custom or ready-made by LangChain) as a tool in the following way:

[Click here to view code image](ch04_images.xhtml#f0100-01)

```
template = "Write a summary in max 3 sentences of the following text: {input}"
human_message_prompt = HumanMessagePromptTemplate(prompt=PromptTemplate(template=template,
input_variables=["input"]))
chat_prompt_template = ChatPromptTemplate.from_messages([human_message_prompt])
llm = AzureChatOpenAI(temperature=0.3, deployment_name=deployment_name)

summary_chain = LLMChain(llm=llm, prompt=chat_prompt_template)

get_summary = Tool.from_function(
        func=summary_chain.run,
        name="Summary",
        description="Summarize the provided text.",
        return_direct=False # If true the output of the tool is returned directly to the user
)
```

Once you have configured the tools, you just need to build the agent:

[Click here to view code image](ch04_images.xhtml#f0101-00)

```
tools = [get_top3_results, get_word_length, get_number_words, get_summary]
agent = initialize_agent(
        tools,
        llm,
        agent=AgentType.OPENAI_FUNCTIONS,
        verbose=True,
        #If false, an exception will be raised every time the output parser can't parse LLM/tool
output
        handle_parsing_errors=True
)
```

You can run it with the following code:

[Click here to view code image](ch04_images.xhtml#f0101-01)

```
agent.run("How many words does the title of Nietzsche's first manuscript contain?")
```

This would probably output something like the following:

[Click here to view code image](ch04_images.xhtml#f0101-02)

```
> Entering new AgentExecutor chain...
Invoking: `get_number_words` with `{'str': "Nietzsche's first manuscript"}`
3The title of Nietzsche's first manuscript contains 3 words.
> Finished chain.
"The title of Nietzsche's first manuscript contains 3 words."
```

As you can see from the log, this agent type (`OPENAI_FUNCTIONS`) might not be the best one because it doesn’t actively search on the web for the title of Nietzsche’s first manuscript. Instead, because it misunderstands the request, it relies more on tools than on factual reasoning.

You could add an entirely custom prompt miming the ReAct framework, initializing the agent executor in a different way. But an easier approach would be to try with a different agent type: `CHAT_ZERO_SHOT_REACT_DESCRIPTION`.

Sometimes the retrieved information might not be accurate, so a second fact-checking step may be needed. You can achieve this by adding more tools (like Wikipedia’s tools or Wikipedia’s docstore and the `REACT_DOCSTORE` agent), using the `SELF_ASK_WITH_SEARCH` agent, or adding a fact-checking chain as a tool and slightly modifying the base prompt to add this additional fact-checking step. Editing the base prompt can be done as follows:

[Click here to view code image](ch04_images.xhtml#f0101-03)

```
agent_chain = initialize_agent(
        tools,
        llm,
        agent=AgentType.CHAT_ZERO_SHOT_REACT_DESCRIPTION,
        verbose=True,
        handle_parsing_errors=True,
        agent_kwargs={
                'system_message_suffix':"Begin! Reminder to always use the exact characters
`Final Answer` when responding. Before returning the final answer, translate it to French."
        }
)
```

Looking at the agent’s source code is helpful for identifying which parameter to use within `agent_kwargs`. In this case, you used `system_message_suffix`, but `system_message_prefix` and `human_message` (which must contain at least `"{input}\n\n{agent_scratchpad}"`) are also editable. One more thing that can be modified is the output parser, as the agent calls the LLM, parses the output, adds the parsed result (if any) to `agent_scratchpad`, and repeats until the final answer is found.

The same results can be achieved using LCEL, in a similar manner:

[Click here to view code image](ch04_images.xhtml#f0102-01)

```
from langchain.tools.render import format_tool_to_openai_function
llm_with_tools = llm.bind(functions=[format_tool_to_openai_function(t) for t in tools])
from langchain.agents.format_scratchpad import format_to_openai_function_messages
from langchain.agents.output_parsers import OpenAIFunctionsAgentOutputParser
from langchain.agents import AgentExecutor

agent = (
    {
        "input": lambda x: x["input"],
        "agent_scratchpad": lambda x: format_to_openai_function_messages(
            x["intermediate_steps"]
        ),
    }
    | prompt
    | llm_with_tools
    | OpenAIFunctionsAgentOutputParser()
)

agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True)
agent_executor.invoke({"input": "how many letters in the word educa?"})
```

![image](/api/v2/epubs/urn:orm:book:9780138280383/files/graphics/note.jpg) Note

The `agent` instance defined above outputs an *`AgentAction`*, so we need an *`AgentExecutor`* to execute the actions requested by the agent (and to make some error handling, early stopping, tracing, etc.).

##### Memory

The preceding sample used `CHAT_ZERO_SHOT_REACT_DESCRIPTION`. In this context, *zero shot* means that there’s no memory but only a single execution. If we ask, “What was Nietzsche’s first book?” and then ask, “When was it published?” the agent wouldn’t understand the follow-up question because it loses the conversation history at every interaction.

Clearly, a conversational approach with linked memory is needed. This can be achieved with an agent type like `CHAT_CONVERSATIONAL_REACT_DESCRIPTION` and a LangChain Memory object, like so:

[Click here to view code image](ch04_images.xhtml#f0102-02)

```
from langchain.memory import ConversationBufferMemory
# return_messages=True is key when we use ChatModels
memory = ConversationBufferMemory(memory_key="chat_history", return_messages=True)
agent = initialize_agent(
    tools,
    llm,
    agent=AgentType.CHAT_CONVERSATIONAL_REACT_DESCRIPTION,
    verbose=True,
    handle_parsing_errors = True,
    memory = memory
)
```

![image](/api/v2/epubs/urn:orm:book:9780138280383/files/graphics/note.jpg) Note

If we miss `return_messages=True` the agent won’t work with Chat Models. In fact, this option instructs the `Memory` object to store and return the full `BaseMessage` instance instead of plain strings, and this is exactly what a Chat Model needs to work.

If you want to explore the full ReAct prompt, you can do so with the following code:

[Click here to view code image](ch04_images.xhtml#f0103-01)

```
for message in agent_executor.agent.llm_chain.prompt.messages:
     try:
          print(message.prompt.template)
     except AttributeError:
          print(f'{{{message.variable_name}}}')
```

The final prompt is:

[Click here to view code image](ch04_images.xhtml#f0103-02)

```
Assistant is a large language model trained by OpenAI.
Assistant is designed to be able to assist with a wide range of tasks, from answering simple
questions to providing in-depth explanations and discussions on a wide range of topics. As a
language model, Assistant is able to generate human-like text based on the input it receives,
allowing it to engage in natural-sounding conversations and provide responses that are coherent
and relevant to the topic at hand.

Assistant is constantly learning and improving, and its capabilities are constantly evolving. It
is able to process and understand large amounts of text, and can use this knowledge to provide
accurate and informative responses to a wide range of questions. Additionally, Assistant is able
to generate its own text based on the input it receives, allowing it to engage in discussions
and provide explanations and descriptions on a wide range of topics.

Overall, Assistant is a powerful system that can help with a wide range of tasks and provide
valuable insights and information on a wide range of topics. Whether you need help with a
specific question or just want to have a conversation about a particular topic, Assistant is
here to assist.

{chat_history}

TOOLS
------
Assistant can ask the user to use tools to look up information that may be helpful in answering
the user's original question. The tools the human can use are:

> GoogleSearch: Search Google for relevant and recent results.
> get_word_length: get_word_length(word: str) -> int - Returns the length, in terms of
characters, of a string.
> get_number_words: get_number_words(str: str) -> int - Returns the number of words of a string.
> Summary: Summarize the provided text.

RESPONSE FORMAT INSTRUCTIONS
----------------------------
When responding to me, please output a response in one of two formats:
**Option 1:**
Use this if you want the human to use a tool.
Markdown code snippet formatted in the following schema:
```json
{{
      "action": string, \ The action to take. Must be one of GoogleSearch,
get_word_length, get_number_words, Summary
      "action_input": string \ The input to the action
}}
```

**Option #2:**
Use this if you want to respond directly to the human. Markdown code snippet formatted in the
following schema:
```json
{{
      "action": "Final Answer",
      "action_input": string \ You should put what you want to return to use here
}}
```

USER'S INPUT
--------------------
Here is the user's input (remember to respond with a markdown code snippet of a json blob with a
single action, and NOTHING else):
{input}
{agent_scratchpad}
```

Running `agent.run("what's the last book of Nietzsche?")` and `agent.run("when was it written?")`, you correctly get, respectively: `The last book written by Friedrich Nietzsche is 'Ecce Homo: How One Becomes What One Is'` and `'Ecce Homo: How One Becomes What One Is' was written in 1888`.

When working with custom agents, remember that the `memory_key` of the `ConversationalMemory` object property must match the placeholder in the prompt template message.

For production purposes, you might want to store the conversation in some kind of database, like Redis through the `RedisChatMessageHistory` class.

#### Data connection

LangChain offers a comprehensive set of features for connecting to external data sources, especially for summarization purposes and for RAG applications. With RAG applications, retrieving external data is a crucial step before model generation.

LangChain covers the entire retrieval process, including document loading, transformation, text embedding, vector storage, and retrieval algorithms. It includes diverse document loaders, efficient document transformations, integration with multiple text embedding models and vector stores, and a variety of retrievers. These offerings enhance retrieval methods from semantic search to advanced algorithms like `ParentDocumentRetriever`, `SelfQueryRetriever`, and `EnsembleRetriever`.

##### Loaders and transformers

LangChain supports various loaders, including the following:

- **TextLoader** and **DirectoryLoader** These load text files within entire directories or one by one.
- **CSVLoader** This is for loading CSV files.
- **UnstructuredHTMLLoader** and **BSHTMLLoader** These load HTML pages in an unstructured form or using BeautifulSoup4.
- **JSONLoader** This loads JSON and JSON Lines files. (This loader requires the jq python package.)
- **UnstructuredMarkdownLoader** This loads markdown pages in an unstructured form. (This loader requires `unstructured` Python package.)
- **PDF loaders** These include PyPDFLoader (which requires `pypdf`), PyMuPDFLoader, UnstructuredPDFLoader, PDFMinerLoader, PyPDFDirectoryLoader, and more.

As an example, after running the Python command `pip install pypdf`, you could load a PDF file within your working directory and show its first page in this way:

[Click here to view code image](ch04_images.xhtml#f0105-01)

```
from langchain.document_loaders import PyPDFLoader
loader = PyPDFLoader("bitcoin.pdf")
pages = loader.load_and_split() #load_and_split breaks the document down into pages, while load
keeps it together
pages[0]
```

Once the loading step is done, you usually want to split long documents into smaller chunks and, more generally, apply some transformation. With lengthy texts, segmenting it into chunks is essential, although this process can be intricate. Maintaining semantically connected portions of text is crucial, but precisely how you do this varies based on the text’s type. A crucial point is to allow for some overlapping between different chunks to add context—for example, always re-adding the last N characters or the last N sentences.

LangChain offers text splitters to divide text into meaningful units—often sentences, but not always (think about code). These units are then combined into larger chunks. When a size threshold (measured in characters or tokens) is met, they become separate text pieces, with some overlap for context.

Here is an example using `RecursiveCharacterTextSplitter`:

[Click here to view code image](ch04_images.xhtml#f0105-02)

```
from langchain.text_splitter import RecursiveCharacterTextSplitter

text_splitter = RecursiveCharacterTextSplitter(
     # small chunk size
     chunk_size = 350,
     chunk_overlap  = 50,
     length_function = len, #customizable
     separators=["\n\n", "\n", "(?<=\. )", " ", ""]
)
```

As shown, you can add custom separators and regular expressions. Native support for token-based markdown and code splitting is included.

LangChain also offers integration with doctran (*[https://github.com/psychic-api/doctran/tree/main](https://github.com/psychic-api/doctran/tree/main)*) to manipulate documents and apply general transformation, like translations, summarization, refining, and so on. For example, the code to translate a document using doctran, after running the `pip install doctran` command, is as follows:

[Click here to view code image](ch04_images.xhtml#f0106-01)

```
from langchain.schema import Document
from langchain.document_transformers import DoctranTextTranslator
qa_translator = DoctranTextTranslator(language="spanish", openai_api_model=deployment_name)
translated_document = await qa_translator.atransform_documents(pages)
```

![image](/api/v2/epubs/urn:orm:book:9780138280383/files/graphics/note.jpg) Note

Unfortunately, at this time, LangChain’s Doctran implementation supports only OpenAI models. Azure OpenAI models are not supported.

##### Embeddings and vector stores

Before connecting to vector stores, you must embed your documents. To achieve this, LangChain offers an entire `Embeddings` module, which serves as an interface to various text embedding models. This streamlines interactions with providers such as OpenAI, Azure OpenAI, Cohere, and Hugging Face. As described in the previous chapter, in the discussion about generating vector representations of text, this class enables semantic search and similar text analysis in vector space.

The core `Embeddings` class within LangChain offers two distinct methods: one for embedding documents and another for embedding queries. The distinction arises from variations among embedding providers in their approach to documents and search queries:

[Click here to view code image](ch04_images.xhtml#f0106-02)

```
from langchain.embeddings import AzureOpenAIEmbeddings
import os
os.environ["OPENAI_API_TYPE"] = "azure"
os.environ["AZURE_OPENAI_API_VERSION"] = "2023-12-01-preview"
os.environ["AZURE_OPENAI_ENDPOINT"] = os.getenv("AOAI_ENDPOINT")
os.environ["AZURE_OPENAI_KEY"] = os.getenv("AOAI_KEY")
embedding_deployment_name=os.getenv("AOAI_EMBEDDINGS_DEPLOYMENTID")

embedding_model = AzureOpenAIEmbeddings(azure_deployment=embedding_deployment_name)
embeddings = embedding_model.embed_documents(["My name is Francesco", "Hello World"])
#or
#embeddings = embeddings_model.embed_query("My name is Francesco")
```

To execute this code, you also need to run `pip install tiktoken`.

Let’s play with vector stores by importing the splits created from the Bitcoin.pdf and executing `pip install chromadb`.

![image](/api/v2/epubs/urn:orm:book:9780138280383/files/graphics/note.jpg) Note

If you get a “Failed to build hnswlib ERROR: Could not build wheels for hnswlib, which is required to install pyproject.toml-based projects” error and a “clang: error: the clang compiler does not support ’-march=native’” error, then set the following `ENV` variable:

```
export HNSWLIB_NO_NATIVE=1
```

With Chroma installed, let’s run the following code to configure (and persist) the vector store:

[Click here to view code image](ch04_images.xhtml#f0107-01)

```
from langchain.vectorstores import Chroma
persist_directory = 'store/chroma/'

vectordb = Chroma.from_documents(
    documents=splits,
    embedding=embedding_model,
    persist_directory=persist_directory
)
vectordb.persist()
```

Finally, query it as follows:

[Click here to view code image](ch04_images.xhtml#f0107-02)

```
vectordb.similarity_search("how is implemented the proof of work ",k=3)
```

You should get the following output:

[Click here to view code image](ch04_images.xhtml#f0107-03)

```
[Document(page_content="4.Proof-of-Work\nTo implement a distributed timestamp server on a peer-
to-peer basis, we will need to use a proof-\nof-work system similar to Adam Back's Hashcash [6],
rather than newspaper or Usenet posts.  \nThe proof-of-work involves scanning for a value that
when hashed, such as with SHA-256, the", metadata={'page': 2, 'source': 'bitcoin.pdf'})

Document(page_content='The steps to run the network are as follows:\n1)New transactions are
broadcast to all nodes.\n2)Each node collects new transactions into a block.  \n3)Each node
works on finding a difficult proof-of-work for its block.\n4)When a node finds a proof-of-work,
it broadcasts the block to all nodes.', metadata={'page': 2, 'source': 'bitcoin.pdf'}),

Document(page_content='would include redoing all the blocks after it.\nThe proof-of-work also
solves the problem of determining representation in majority decision  \nmaking.  If the
majority were based on one-IP-address-one-vote, it could be subverted by anyone  \nable  to
allocate  many  IPs.   Proof-of-work  is  essentially  one-CPU-one-vote.   The  majority',
metadata={'page': 2, 'source': 'bitcoin.pdf'})]
```

![image](/api/v2/epubs/urn:orm:book:9780138280383/files/graphics/note.jpg) Note

This example used Chroma. However, LangChain supports several other vector stores, and its interface abstracts over all of them. (For more details, see *[https://python.langchain.com/docs/integrations/vectorstores/](https://python.langchain.com/docs/integrations/vectorstores/)*.)

##### Retrievers and RAG

The previous code snippet performed a plain similarity search. But as mentioned, there are other options, such as using maximum marginal relevance (MMR), to enforce diversity within query results:

[Click here to view code image](ch04_images.xhtml#f0107-04)

```
vectordb.max_marginal_relevance_search("how is implemented the proof of work",k=3)
```

Querying on metadata is also possible:

[Click here to view code image](ch04_images.xhtml#f0108-01)

```
vectordb.similarity_search(
     "how is implemented the proof of work",
     k=3,
     filter={"page":4 }
)
```

Leveraging metadata filtering, you can involve a `SelfQueryRetriever` (with LARK installed), which has access to the vector store and uses an LLM to generate metadata filters:

[Click here to view code image](ch04_images.xhtml#f0108-02)

```
from langchain.retrievers.self_query.base import SelfQueryRetriever
from langchain.chains.query_constructor.base import AttributeInfo
from langchain.chat_models import AzureChatOpenAI
metadata_field_info = [
    AttributeInfo(
        name="source",
        description="The document name. At the moment it can only be bitcoin.pdf`",
        type="string",
    ),
    AttributeInfo(
        name="page",
        description="The page from the document",
        type="integer",
    ),
]
llm = AzureChatOpenAI(temperature=.3, azure_deployment=deployment_name)
retriever = SelfQueryRetriever.from_llm(
    llm,
    vectordb,
    "Bitcoin whitepaper",
    metadata_field_info,
    verbose=True
)
docs = retriever.get_relevant_documents("how is implemented the proof of work")
```

One more approach for retrieving better-quality documents is to use compression. This involves including a `ContextualCompressionRetriever` and an `LLMChainExtractor` to extract relevant information from a lot of documents (using an LLM chain) before passing it to the RAG part.

Independently from the model’s architecture, performance degrades substantially when more than 10 documents are included in the LLM’s window context. This is because the model has to gather relevant information in the middle of very long contexts, so it ignores pieces of provided documents. You can fix this by reranking documents, putting less relevant ones in the middle and more relevant ones at the beginning and end.

Essentially, a vector store leverages its index to build a retriever, but vector stores indexes are not the only way to build a retriever (which is, ultimately, used for RAG). For instance, LangChain supports SVM and TF-IDF (with scikit installed), and several other retrievers:

[Click here to view code image](ch04_images.xhtml#f0108-03)

```
from langchain.retrievers import SVMRetriever
from langchain.retrievers import TFIDFRetriever

svm_retriever = SVMRetriever.from_documents(splits,embedding_model)
tfidf_retriever = TFIDFRetriever.from_documents(splits)
docs_svm=svm_retriever.get_relevant_documents("how is implemented the proof of work")
docs_tfidf=tfidf_retriever.get_relevant_documents("how is implemented the proof of work")
```

##### Retrieval augmented generation

Putting everything together in the RAG use case, the final code is as follows:

[Click here to view code image](ch04_images.xhtml#f0109-01)

```
from langchain.memory import ConversationBufferMemory
from langchain.chains import ConversationalRetrievalChain
memory = ConversationBufferMemory(memory_key="chat_history",return_messages=True)
llm = AzureChatOpenAI(temperature=.3, azure_deployment =deployment_name)
retriever=vectordb.as_retriever()
qa = ConversationalRetrievalChain.from_llm(llm,retriever=retriever,memory=memory)
question = "how is implemented the proof of work"
result = qa({"question": question})
result['answer']
```

This yields a reasonable answer to the question (“How is the proof of work implemented?”):

[Click here to view code image](ch04_images.xhtml#f0109-02)

```
The proof-of-work in this context is implemented using a system similar to Adam Back's Hashcash.
It involves scanning for a specific value that, when hashed (using SHA-256, for example), meets
certain criteria. This process requires computational effort and serves as a way to secure
and validate transactions on the network. When a node successfully finds a proof-of-work, it
broadcasts the block containing the proof-of-work to all other nodes in the network
```

![image](/api/v2/epubs/urn:orm:book:9780138280383/files/graphics/note.jpg) Note

As usual, you can substitute the memory, retriever, and LLM with any of the discussed options, using hosted models, summary memory, or an SVM retriever.

This code works, but it’s far from being a production-ready product. It needs to be embedded in a real chat (with UI, login, and so on); user-specific memory needs to be implemented; the database load should be balanced with resources; and handlers, fallbacks, and loggers need to be added. In short, the traditional software and engineering aspects are missing to transform this intriguing experiment into a functional product.

![image](/api/v2/epubs/urn:orm:book:9780138280383/files/graphics/note.jpg) Note

LlamaIndex is a competitor to LangChain for RAG. It is a specialized library for data ingestion, data indexing, and query interfaces, making it easy to build an LLM app with the RAG pattern from scratch.

### Microsoft Semantic Kernel

Semantic Kernel (SK) is a lightweight SDK that empowers developers to seamlessly blend traditional programming languages (C#, Python, and Java) with the cutting-edge capabilities of LLMs. Like LangChain, SK also works as an LLM orchestrator.

SK has similar features to LangChain, like prompt templating, chaining, and planning to enable the creation of agents. Like LangChain, SK also distinguishes between text completion–based and chat-based models, with slightly different interfaces.

Base use cases for SK range from summarizing lengthy conversations and adding important tasks to a to-do list, to orchestrating complex tasks like planning a vacation. SK’s design revolves around plug-ins (formerly known as *skills*), which developers can build as semantic or native code modules. These plug-ins work in conjunction with SK’s memories for context and connectors for live data and actions. An SK planner receives a user’s request and translates it into the required plug-ins, memories, and connectors to achieve the desired outcome.

![image](/api/v2/epubs/urn:orm:book:9780138280383/files/graphics/note.jpg) Note

During its genesis, SK used different names to refer to the same thing—specifically to plug-ins, skills, and functions. Eventually, SK settled on plug-ins. However, although SK’s documentation consistently uses this term, its code sometimes still reflects the old conventions.

SK supports models directly from OpenAI, Azure OpenAI, and Hugging Face, and it is open source on GitHub.

The main pieces of SK are as follows:

- **Kernel** This is a wrapper that runs a pipeline/chain defined by the developer.
- **KernelArguments** This the common abstract context injected into the kernel.
- **Semantic memory** This is the connector used to store and retrieve context in vector databases.
- **Plug-ins** These consist of a group of semantic functions (LLM prompts), native functions (native code), and connectors. They can be conceptually organized into two different groups (although these are technically equivalent):
  - **Connectors** You use these to get additional data or to perform additional actions (like MS Graph API, Open API, web scrapers, or custom-made connectors). Think of these as the equivalent of LangChain’s toolkits, wrapping together different functions.
  - **Functions** These can be semantic (defined by a prompt) or native (proper code). They are equivalent to LangChain’s tools.
- **Planner** This is the equivalent of a LangChain agent. It’s used to auto-create chains using preloaded functions and connectors.

![image](/api/v2/epubs/urn:orm:book:9780138280383/files/graphics/note.jpg) Note

For lots of examples of each of these components, curated by the SK development team, see *[https://github.com/microsoft/semantic-kernel/tree/main/dotnet/samples/KernelSyntaxExamples](https://github.com/microsoft/semantic-kernel/tree/main/dotnet/samples/KernelSyntaxExamples)*.

SK has embraced the OpenAI plug-in specification to establish a universal standard for plug-ins. This initiative aims to foster a cohesive ecosystem of compatible plug-ins that can seamlessly function across prominent AI applications and services such as ChatGPT, Bing, and Microsoft 365. Developers leveraging SK can thereby extend the usability of their plug-ins to these platforms without the need for code rewrites. Furthermore, plug-ins designed for ChatGPT, Bing, and Microsoft 365 can be integrated with SK, promoting cross-platform plug-in interoperability.

![image](/api/v2/epubs/urn:orm:book:9780138280383/files/graphics/note.jpg) Note

This chapter uses SK version 1.0.1. SK LangChain appears more stable than SK. Therefore, the code provided here has been minimized to the essential level, featuring only a few key snippets alongside core concepts. It is hoped that these foundational elements remain consistent over time.

#### Plug-ins

At a fundamental level, a *plug-in* is a collection of functions designed to be harnessed by AI applications and services. These functions serve as the application’s building blocks when handling user queries and internal demands. You can activate functions—and by extension, plug-ins—manually or automatically through a planner.

Each function must be furnished with a comprehensive semantic description detailing its behavior. This description should articulate the entirety of a function’s characteristics—including its inputs, outputs, and potential side effects—in a manner that the LLM(s) under the chain or planner can understand. This semantic framework is pivotal to ensuring that the planner doesn’t produce unexpected outcomes.

In summary, a plug-in is a repository of functions that serve as functional units within AI apps. Their effectiveness in automated orchestration hinges on comprehensive semantic descriptions. These descriptions enable planners to intelligently choose the best function for each circumstance, resulting in smoother and more tailored user experiences.

##### Kernel configuration

Before you can use SK in a real-world app, you must add its NuGet package. To do so, use the following command in a C# Polyglot notebook:

[Click here to view code image](ch04_images.xhtml#f0111-01)

```
#r "nuget: Microsoft.SemanticKernel, *-*"
```

![image](/api/v2/epubs/urn:orm:book:9780138280383/files/graphics/note.jpg) Note

You might also need to add Microsoft.Extensions.Logging, Microsoft.Extensions. Logging.Abstractions, and Microsoft.Extensions.Logging.Console.

[Click here to view code image](ch04_images.xhtml#f0111-02)

```
using Microsoft.SemanticKernel;
using System.Net.Http;
using Microsoft.Extensions.Logging;
using System.Diagnostics;
using System.Threading.Tasks;
using Microsoft.Extensions.DependencyInjection;

var httpClient = new HttpClient();

IKernelBuilder builder = Kernel.CreateBuilder();
builder.AddAzureOpenAIChatCompletion(
                    deploymentName: AOAI_DEPLOYMENTID,
                    endpoint: AOAI_ENDPOINT,
                    apiKey: AOAI_KEY,
                    httpClient: httpClient);
builder.Services.AddLogging(c => c.AddConsole().SetMinimumLevel(LogLevel.Information));
Kernel kernel = builder.Build();
```

As shown, you can specify a logging behavior, but also a specific `HttpClient` implementation. Outside a .NET Interactive Notebook, the `HttpClient` should be inserted, along with the kernel, in a `using` statement.

![image](/api/v2/epubs/urn:orm:book:9780138280383/files/graphics/note.jpg) Note

Like LangChain, SK supports integration with models other than Azure OpenAI models. For example, you can easily connect Hugging Face models.

By default, the kernel incorporates automatic retry mechanisms for transient errors like throttling and timeouts during AI invocation.

![image](/api/v2/epubs/urn:orm:book:9780138280383/files/graphics/note.jpg) Note

The kernel’s role is pivotal because it’s the only place where you can configure LLM services. However, there are different ways to use it. For example, you can invoke functions and planners by passing a kernel into their definition or via the `fluent` method `RunAsync` on the kernel instance itself.

##### Semantic or prompt functions

As their name suggests, semantic (or prompt) functions are explicitly described through a prompt. Along with native functions, semantic functions constitute the fundamental building blocks of plug-ins.

There are two ways to define and execute semantic functions: through configuration via files and through inline definition. There are also native plug-ins available under the namespace Microsoft.SemanticKernel.CoreSkills.

Inline configuration is straightforward:

[Click here to view code image](ch04_images.xhtml#f0112-01)

```
using Microsoft.SemanticKernel.Connectors.OpenAI;
var FunctionDefinition = "User: {{$input}} \n From the user input, provide its intent. The
intent should be one of the following: Email, PhoneCall, OnlineMeeting, InPersonMeeting.";

var getIntentFunction = kernel.CreateFunctionFromPrompt(
          FunctionDefinition, new OpenAIPromptExecutionSettings { MaxTokens = 200,
Temperature = 0.3, TopP = 1});

var result = await getIntentFunction.InvokeAsync(kernel, new()
         { ["input"] = "What about a video call this week?" });
Console.WriteLine(result);
```

To add more input variables, you can play with `KernelArguments`:

[Click here to view code image](ch04_images.xhtml#f0113-01)

```
var FunctionDefinition = "User: {{$input}} \n From the user input, provide its intent. The
intent should be one of the following: {{$options}}.";
var getIntentFunction = kernel.CreateSemanticFromPrompt(FunctionDefinition, maxTokens: 200,
temperature: 0.3, topP: 1);
var variables = new KernelArguments();
variables.Add("input", "What about a video call this week?");
variables.Add("options", "Email, PhoneCall, OnlineMeeting, InPersonMeeting");
var result = await getIntentFunction.InvokeAsync(kernel, variables);
```

These variables are visible to functions and can be injected into semantic prompts with `{{variableName}}`.

For real-world projects, you may want to configure a prompt function with separate files. Those configuration files should be structured as in the following schema:

[Click here to view code image](ch04_images.xhtml#f0113-02)

```
Within a Plugins folder
|
﹂Place a {PluginName}Plugin folder
     |
     ﹂ Create a {SemanticFunctionName} folder
          |
          ﹂ config.json
          ﹂ skprompt.txt
```

The skprompt.txt file should contain the prompt, as with the inline definition, while the config.json file should follow this structure:

[Click here to view code image](ch04_images.xhtml#f0113-03)

```
{
     "schema": 1,
     "type": "completion",
     "description": "Creates a chat response to the user",
     "execution_settings": {
        "default": {
          "max_tokens": 1000,
          "temperature": 0
        },
        "gpt-4": {
          "model_id": "gpt-4-1106-preview",
          "max_tokens": 8000,
          "temperature": 0.3
        }
      },
     "input_variables": [
        {
          "name": "request",
          "description": "The user's request.",
         "required": true
        },
        {
          "name": "history",
          "description": "The history of the conversation.",
          "required": true
        }
     ]
}
```

To call a file-defined function, use the following:

[Click here to view code image](ch04_images.xhtml#f0114-01)

```
var pluginsDirectory = Path.Combine(System.IO.Directory.GetCurrentDirectory(), "path", "to",
"plugins", "folder");
var basePlugin = kernel.CreatePluginFromPromptDirectory(kernel, pluginsDirectory, "PLUGINNAME");
var result = await basePlugin["FunctionName"].InvokeAsync(kernel, variables);
```

The file definition aims to generalize the function definition. It is strictly linked to the plug-in definition, covered shortly.

##### Native functions

Native functions are defined via code and can be seen as the deterministic part of a plug-in. Like prompt functions, a native function can be defined in a file whose path follows this schema:

[Click here to view code image](ch04_images.xhtml#f0114-02)

```
Within a Plugins folder
|
﹂ Place a {PluginName}Plugin folder
     |
###############
      ﹂ Create a {SemanticFunctionName} folder
          |
           ﹂ config.json
           ﹂ skprompt.txt
     |
      ﹂ {PluginName}Plugin.cs file that contains all the native functions for a given plug-in
```

Here’s a simple version of a native function:

[Click here to view code image](ch04_images.xhtml#f0114-03)

```
public class MathPlugin
{
    [KernelFunction, Description("Takes the square root of a number")]
    public string Sqrt(string number)
    {
        return Math.Sqrt(Convert.ToDouble(number)).ToString();
    }
}
```

Taking a single input, there’s no need to specify anything beyond the function description. The planner (agent) can then use this to decide whether to call the function.

Here’s an example with more input parameters:

[Click here to view code image](ch04_images.xhtml#f0114-04)

```
[KernelFunction, Description("Adds up two numbers")]
public int Add(
     [Description("The first number to add")] int number1,
     [Description("The second number to add")] int number2)
        => number1 + number2;
```

To invoke native functions, you can take the following approach:

[Click here to view code image](ch04_images.xhtml#f0115-01)

```
var result2 = await mathPlugin["Add"].InvokeAsync(kernel, new (){ {"number1", 15},
{ "number2", "7" } });
Console.WriteLine(result2);
```

Essentially, you first import the implicitly defined plug-in into the kernel and then call it.

If the `InvokeAsync` method has only a single input, you must pass a string and take care of the conversion inside the function body. Alternatively, you can use `ContextVariables` and let the framework convert the inputs.

Based on their internal logic—which can involve any piece of software you might need, including software to connect to databases, send emails, and so on—native functions typically return a string. Alternatively, they can simply perform an action, such as a type of void or task.

In the real world, native functions have three different use cases:

- Deterministic transformations to input or output, being chained with more semantic functions
- Action executors, after a semantic function has understood the user intent
- Tools for planners/agents

In addition, if you pass a `Kernel` object to the plug-in containing your function, you can call prompt functions from native ones.

##### Core plug-ins

By putting together prompt and native functions, you build a custom-made plug-in. In addition, SK comes with core plug-ins, under Microsoft.SemanticKernel.CoreSkills:

- **ConversationSummarySkill** Used for summarizing conversations
- **FileIOSkill** Handles reading and writing to the file system
- **HttpSkill** Enables API calls
- **MathSkill** Performs mathematical operations
- **TextMemorySkill** Stores and retrieves text in memory
- **TextSkill** For deterministic text manipulation (uppercase, lowercase, trim, and so on)
- **TimeSkill** Obtains time-related information
- **WaitSkill** Pauses execution for a specified duration

These plug-ins can be imported into the kernel in the normal manner and then used in the same way as user-defined ones:

[Click here to view code image](ch04_images.xhtml#f0115-02)

```
kernel.AddFromType<TimePlugin>("Time");
```

OpenAPI plug-ins are very useful. Through the `ImportPluginFromOpenApiAsync` method on the kernel, you can call any API that follows the OpenAPI schema. This will be further expanded in [Chapter 8](ch08.xhtml#ch08).

One interesting feature is that after a plug-in is imported into the kernel, you can reference functions (native and semantic) in a prompt with the following syntax: `{{PluginName.FunctionName $variableName}}`. (For more information, see *[https://learn.microsoft.com/en-us/semantic-kernel/prompts/calling-nested-functions](https://learn.microsoft.com/en-us/semantic-kernel/prompts/calling-nested-functions)*.)

#### Data and planners

To operate effectively, a planner (or agent) needs access to tools that allow it to “do things.” Tools include some form of memory, orchestration logic, and finally, the goal provided by the user. You have already constructed the tools (namely the plug-ins); now it’s time to address the memory, data, and actual construction of the planner.

##### Memory

SK has no distinct separation between long-term memory and conversational memory. In the case of conversational memory, you must build your own custom strategies (like LangChain’s summary memory, entity memory, and so on). SK supports several memory stores:

- Volatile (This simulates a vector database). It shouldn’t be used in a production environment, but it’s very useful for testing and proof of concepts (POCs).
- AzureCognitiveSearch (This is the only memory option with a fully managed service within Azure.)
- Redis
- Chroma
- Kusto
- Pinecone
- Weaviate
- Qdrant
- Postgres (using `NpgsqlDataSourceBuilder` and the `UseVector` option)
- More to come…

You can also build out a custom memory store, implementing the `ImemoryStore` interface and combining it with embedding generation and searching by some similarity function.

You need to instantiate a memory plug-in on top of a memory store so it can be used by a planner or other plug-ins to recall information:

[Click here to view code image](ch04_images.xhtml#f0116-01)

```
using Microsoft.SemanticKernel.Skills.Core;
var memorySkill = new TextMemorySkill(kernel.Memory);
kernel.ImportSkill(memorySkill);
```

`TextMemorySkill` is a plug-in with native functions. It facilitates the saving and recalling of information from long-term or short-term memory. It supports the following methods:

- **RetrieveAsync** This performs a key-based lookup for a specific memory.
- **RecallAsync** This enables semantic search and return of related memories based on input text.
- **SaveAsync** This saves information to the semantic memory.
- **RemoveAsync** This removes specific memories.

All these methods can be invoked on the kernel, like so:

[Click here to view code image](ch04_images.xhtml#f0117-01)

```
        result = await kernel.InvokeAsync(memoryPlugin["Recall"], new()
        {
            [TextMemoryPlugin.InputParam] = "Ask: what's my name?",
            [TextMemoryPlugin.CollectionParam] = MemoryCollectionName,
            [TextMemoryPlugin.LimitParam] = "2",
            [TextMemoryPlugin.RelevanceParam] = "0.79",
        });
        Console.WriteLine($"Answer: {result.GetValue<string>()}");
```

You can also define a semantic function, including the recall method within the prompt, and build up a naïve RAG pattern:

[Click here to view code image](ch04_images.xhtml#f0117-02)

```
var recallFunctionDefinition = @"
Using ONLY the following information and no prior knowledge, answer the user's questions:
---INFORMATION---
{{recall $input}}
-----------------
Question: {{$input}}
Answer:";
var recallFunction = kernel.CreateFunctionFromPrompt(RecallFunctionDefinition, new
OpenAIPromptExecutionSettings() {
        MaxTokens = 100 });
var answer2 = await kernel. InvokeAsync(recallFunction, new()
{
      [TextMemoryPlugin.InputParam] = " who wrote bitcoin whitepaper?",
     [TextMemorySkill.CollectionParam] = MemoryCollectionName,
     [TextMemoryPlugin.LimitParam] = "2",
     [TextMemorySkill.RelevanceParam] = "0.85"
});
Console.WriteLine("Ask: who wrote bitcoin whitepaper?");
Console.WriteLine("Answer:\n{0}", answer2);
```

The output is something like:

[Click here to view code image](ch04_images.xhtml#f0117-03)

```
Satoshi Nakamoto wrote the Bitcoin whitepaper in 2008
```

##### SQL access within SK

LangChain has its own official SQL connector to execute queries on a database. However, currently, SK doesn’t have its own plug-in.

Making direct SQL access is key when:

- Dynamic data is required.
- Prompt grounding is not an option due to token limits.
- Syncing the SQL database with a vector database (over which a similarity search can be easily performed) is not an option because there is no intention to introduce concerns related to consistency or any form of data movement.

Consider the question, “What was the biggest client we had in May?” Even if you had a vector database with sales information, a similarity search wouldn’t help you answer this question, meaning a structured (and deterministic) query should be run.

Microsoft is working on a library (to be used also as a service) called Kernel Memory (*[https://github.com/microsoft/kernel-memory](https://github.com/microsoft/kernel-memory)*). This basically replicates the memory part of SK. The development team is planning to add SQL access directly to SK, but it is still unclear whether an official SQL plug-in will be released as part of the Semantic Memory library or as a core plug-in in SK.

With that said, there is a tentative example from the Semantic Library called Natural Language to SQL (NL2SQL), located here: *[https://github.com/microsoft/semantic-memory/tree/main/examples/200-dotnet-nl2sql](https://github.com/microsoft/semantic-memory/tree/main/examples/200-dotnet-nl2sql)*. This example, which is built as a console app, includes a semantic memory section to obtain the correct database schema (based on the user query and in case there are multiple schemas) over which a T-SQL statement is created by a semantic function and then executed. At the moment, you can only copy and paste parts of this example to build a custom plug-in in SK and use it or give it to a planner.

More generally, with SQL access through LLM-generated queries (GPT 4 is much better than GPT 3.5-turbo for this task), you should prioritize least-privilege access and implement injection-prevention measures to enhance security (more on this in [Chapter 5](ch05.xhtml#ch05)).

##### Unstructured data ingestion

To ingest structured data, the best approach is to build APIs to call (possibly following the OpenAPI schema and using the core plug-in) or to create a plug-in to query the database directly. For unstructured data, such as images, it makes sense to use a dedicated vector store outside SK or to create a custom memory store that also supports images. For textual documents, which are the most common in AI applications, you can leverage tools such as text chunkers, which are natively available in SK.

As an example, you can use `PdfPig` to import PDF files as follows:

[Click here to view code image](ch04_images.xhtml#f0118-01)

```
using UglyToad.PdfPig.DocumentLayoutAnalysis.TextExtractor;
using Microsoft.SemanticKernel.Memory;
using Microsoft.SemanticKernel.Text;

var BitcoinMemoryCollectionName = "BitcoinMemory";
var chunk_size_in_characters = 1024;
var chunk_overlap_in_characters = 200;
var pdfFileName = "bitcoin.pdf";
var pdfDocument = UglyToad.PdfPig.PdfDocument.Open(pdfFileName);
foreach (var pdfPage in pdfDocument.GetPages())
{
    var pageText = ContentOrderTextExtractor.GetText(pdfPage);
    var paragraphs = new List<string>();
    if (pageText.Length > chunk_size_in_characters)
    {
        var lines = TextChunker.SplitPlainTextLines(pageText, chunk_size);
        paragraphs = TextChunker.SplitPlainTextParagraphs(lines, chunk_size_in_characters,
chunk_overlap);
    }
    else
    {
        paragraphs.Add(pageText);
    }
    foreach (var paragraph in paragraphs)
    {
          var id = pdfFileName + pdfPage.Number + paragraphs.IndexOf(paragraph);
          await textMemory.SaveInformationAsync(MemoryCollectionName, id: "info1", text:
"My name is Andrea");
    }
}
pdfDocument.Dispose();
```

This can obviously be extended to any textual document.

##### Planners

Finally, now that you have received a comprehensive overview of the tools you can connect, you can create an agent—or, as it is called in SK, a planner. SK offers two types of planners:

- **Handlebars Planner** This generates a complete plan for a given goal. It is indicated in canonical scenarios with a sequence of steps passing outputs forward. It utilizes Handlebars syntax for plan generation, providing accuracy and support for features like loops and conditions.
- **Function Calling Stepwise Planner** This iterates on a sequential plan until a given goal is complete. It is based on a neuro-symbolic architecture called Modular Reasoning, Knowledge, and Language (MRKL), the core idea behind ReAct. This planner is indicated when adaptable plug-in selection is needed or when intricate tasks must be managed in interlinked stages. Be aware, however, that this planner raises the chances of encountering hallucinations when using 10+ plug-ins.

![image](/api/v2/epubs/urn:orm:book:9780138280383/files/graphics/tip.jpg) Tip

The OpenAI Function Calling feature, seamlessly wrapped around the lower-level API `GetChatMessageContentAsync`, via `GetOpenAIFunctionResponse()`,can be thought of as a single-step planner.

![image](/api/v2/epubs/urn:orm:book:9780138280383/files/graphics/note.jpg) Note

In [Chapter 8](ch08.xhtml#ch08), you will create a booking app leveraging an SK planner.

Because planners can merge functions in unforeseen ways, you must ensure that only intended functions are exposed. Equally important is applying responsible AI principles to these functions, ensuring that their use aligns with fairness, reliability, safety, privacy, and security.

Like LangChain’s agents, under the hood, planners use an LLM prompt to generate a plan—although this final step can be buried under significant orchestration, forwarding, and parsing logic, especially in the stepwise planner.

SK’s planners enable you to configure certain settings, including the following:

- **RelevancyThreshold** The minimum relevancy score for a function to be considered. This value may need adjusting based on the embeddings engine, user ask, step goal, and available functions.
- **MaxRelevantFunctions** The maximum number of relevant functions to include in the plan. This limits relevant functions resulting from semantic search in the plan-creation request.
- **ExcludedPlugins** A list of plug-ins to exclude from the plan-creation request.
- **ExcludedFunctions** A list of functions to exclude from the plan-creation request.
- **IncludedFunctions** A list of functions to include in the plan-creation request.
- **MaxTokens** The maximum number of tokens allowed in a plan.
- **MaxIterations** The maximum number of iterations allowed in a plan.
- **MinIterationTimeMs** The minimum time to wait between iterations in milliseconds.

![image](/api/v2/epubs/urn:orm:book:9780138280383/files/graphics/tip.jpg) Tip

Filtering for relevancy can significantly enhance the overall performance of the planning process and increase your chances of devising successful plans that accomplish intricate objectives.

Generating plans incurs significant costs in terms of latency and tokens (so, money, as usual). However, there’s one approach that saves both time and money, and reduces your risk of producing unintended results: pre-creating (sequential) plans for common scenarios that users frequently inquire about. You generate these plans offline and store them in JSON format within a memory store. Then, when a user’s intent aligns with one of these common scenarios, based on a similarity search, the relevant preloaded plan is retrieved and executed, eliminating the need to generate plans on-the-fly. This approach aims to enhance performance and mitigate costs associated with using planners. However, it can be used only with the more fixed sequential planner, as the stepwise one is too dynamic.

![image](/api/v2/epubs/urn:orm:book:9780138280383/files/graphics/note.jpg) Note

At the moment, SK planners don’t seem to be as good as LangChain’s agents. Planners throw many more parsing errors (particularly the sequential planners with XML plans) than their equivalent, especially with GPT-3.5-turbo (rather than GPT-4).

### Microsoft Guidance

Microsoft Guidance functions as a domain-specific language (DSL) for managing interactions with LLMs. It can be used with different models, including models from Hugging Face.

Guidance resembles Handlebars, a templating language employed in web applications, while additionally ensuring sequential code execution that aligns with the token processing order of the language model. As interactions with models can become costly when prompts are needlessly repetitive, lengthy, or verbose, Guidance’s goal is to minimize the expense of interacting with LLMs while still maintaining greater control over the output.

![image](/api/v2/epubs/urn:orm:book:9780138280383/files/graphics/note.jpg) Note

Guidance also has a module for testing and evaluating LLMs (currently available only for Python).

A competitor of Microsoft Guidance is LMQL, which is a library for procedural prompting that uses types, templates, constraints, and an optimizing runtime.

#### Configuration

To install Guidance, a simple `pip install guidance` command on the Python terminal will suffice. Guidance supports OpenAI and Azure OpenAI models, but also local models in the transformers format, like Llama, StableLM, Vicuna, and so on. Local models support acceleration, which is an internal Guidance technique to cache tokens and optimize the speed of generation.

##### Models

After you install Guidance, you can configure OpenAI models as follows. (Note that the `OPENAI_API_KEY` environment variable must be set.)

[Click here to view code image](ch04_images.xhtml#f0121-01)

```
from guidance import models
import guidance
import os

llm = models.AzureOpenAI(
    model='gpt-3.5-turbo',
    api_type='azure',
    api_key=os.getenv("AOAI_KEY"),
    azure_endpoint=os.getenv("AOAI_ENDPOINT"),
    api_version='2023-12-01-preview',
    caching=False
)
```

You can also use the transformer version of Hugging Face models (special license terms apply) as well as local ones.

##### Basic usage

To start running templated prompts, let’s test this code:

[Click here to view code image](ch04_images.xhtml#f0122-01)

```
program = guidance("""Today is {{dayOfWeek}} and it is{{gen 'weather' max_tokens=3
stop="."}}""", llm=llm)
program(dayOfWeek='Monday')
```

The output should be similar to:

[Click here to view code image](ch04_images.xhtml#f0122-02)

```
Today is a Monday and it is raining
```

Initially, Guidance might resemble a regular templating language, akin to conventional Handlebars templates featuring variable interpolation and logical control. However, unlike with traditional templating languages, Guidance programs use an orderly linear execution sequence that aligns directly with the order of tokens processed by the language model. This intrinsic connection facilitates the model’s capability to generate text (via the `{{gen}}` command) or implement logical control flow choices at any given execution point.

![image](/api/v2/epubs/urn:orm:book:9780138280383/files/graphics/note.jpg) Note

Sometimes, the generation fails, and Guidance silently returns the template without indicating an error. In this case, you can look to the `program._exception` property or the program.log file for more information.

##### Syntax

Guidance’s syntax is reminiscent of Handlebars’ but features some distinctive enhancements. When you use Guidance, it generates a program upon invocation, which you can execute by providing arguments. These arguments can be either singular or iterative, offering versatility.

The template structure supports iterations, exemplified by the `{{#each}}` tag. Comments can be added using the `{{! ... }}` syntax—for example, `{{! This is a comment }}`*.* The following code, taken from Guidance documentation, is a great example:

[Click here to view code image](ch04_images.xhtml#f0122-03)

```
examples = [
{'input': 'I wrote about shakespeare',
'entities': [{'entity': 'I', 'time': 'present'}, {'entity': 'Shakespeare', 'time': '16th
century'}],
'reasoning': 'I can write about Shakespeare because he lived in the past with respect to me.',
'answer': 'No'},
{'input': 'Shakespeare wrote about me',
'entities': [{'entity': 'Shakespeare', 'time': '16th century'}, {'entity': 'I', 'time':
'present'}],
'reasoning': 'Shakespeare cannot have written about me, because he died before I was born',
'answer': 'Yes'}
]
# define the guidance program
program = guidance(
'''{{~! display the few-shot examples ~}}
{{~#each examples}}
Sentence: {{this.input}}
Entities and dates:{{#each this.entities}}
{{this.entity}}: {{this.time}}{{/each}}
Reasoning: {{this.reasoning}}
Anachronism: {{this.answer}}
---
{{~/each}}''', llm=llm)

program(examples=examples)
```

You can nest prompts or programs within each other, streamlining composition. The template employs the `gen` tag to generate text (`{{gen "VARIABLE NAME"}})`, supporting underlying model arguments. Selection is facilitated via the `select` tag, which allows you to present and evaluate options. Here’s an example:

[Click here to view code image](ch04_images.xhtml#f0123-01)

```
program = guidance('''Generate a response to the following email:
{{email}}.
Response:{{gen "response"}}
Is the response above offensive in any way? Please answer with a single word, either "Yes" or
"No".
Answer:{{#select "answer" logprobs='logprobs'}} Yes{{or}} No{{/select}}''', llm=llm)
program(email='I hate tacos')
```

All variables are then accessible via `program["VARIABLENAME"]`.

One more useful command is `geneach`, which you can use to generate a list. (Hidden generation, achieved using the `hidden` tag, enables text generation without display.)

[Click here to view code image](ch04_images.xhtml#f0123-02)

```
program = guidance('''What are the most famous cities in the {{country}}?
Here are the 3 most common commands:
{{#geneach 'cities' num_iterations=3}}
{{@index}}. "{{gen 'this'}}"{{/geneach}}''', llm=llm)
program(country="Italy")
```

The syntax accommodates the generation of multiple instances with `n>1`, resulting in a list-based outcome:

[Click here to view code image](ch04_images.xhtml#f0123-03)

```
program = guidance('''The best thing about the beach is {{~gen 'best' n=3 temperature=0.7
max_tokens=7}}''', llm=llm)
program()
```

Sometimes, you might need to partially execute a program. In that case, you can use the `await` command. It waits for a variable and then consumes it. This command is also useful to break the execution into multiple programs and wait for external calls.

#### Main features

The overall scope of Guidance seems to be technically more limited than that of SK. Guidance does not aim to be a generic, all-encompassing orchestrator with a set of internal and external tools and native functionalities that can fully support an AI application. Nevertheless, because of its templating language, it does enable the construction of structures (JSON, XML, and more) whose syntax is verified. This is extremely useful for calling APIs, generating flows (similar to chain-of-thought, but also ReAct), and performing role-based chats.

With Guidance, it’s also possible to invoke external functions and thus build agents, even though it’s not specifically designed for this purpose. Consequently, the exposed programming interface is rawer compared to LangChain and SK. Guidance also attempts to optimize (or mitigate) issues deeply rooted in the basic functioning of LLMs, such as token healing and excessive latencies. In an ideal world, Guidance could enhance SK (or LangChain), serving as a connector to the underlying models (including local models and Hugging Face models) and adding its features to the much more enterprise-level interface of SK.

In summary, Guidance enables you to achieve nearly everything you might want to do within the context of an AI application, almost incidentally. However, you can think of it as a lower-level library compared to the two already mentioned, and less flexible due to its use of a single, continuous-flow programming interface.

##### Token healing

Guidance introduces a concept called *token healing* to address tokenization artifacts that commonly emerge at the interface between the end of a prompt and the commencement of generated tokens. Efficient execution of token healing requires direct integration and is currently exclusive to the guidance.llms.Transformers (so, not OpenAI or Azure OpenAI).

Language models operate on tokens, which are typically fragments of text resembling words. This token-centric approach affects both the model’s perception of text and how it can be prompted, since every prompt must be represented as a sequence of tokens. Techniques like byte-pair encoding (BPE) used by GPT-style models map input characters to token IDs in a greedy manner. Although effective during training, greedy tokenization can lead to subtle challenges during prompting and inference. The boundaries of tokens generated often fail to align with the prompt’s end, which becomes especially problematic with tokens that bridge this boundary.

For instance, the prompt `"This is a "` completed with `"fine day."` generates `"This is a fine day."`. Tokenizing the prompt `"This is a "` using GPT2 BPE yields `[1212, 318, 257, 220]`, while the extension `"fine day."` is tokenized as `[38125, 1110, 13]`. This results in a combined sequence of `[1212, 318, 257, 220, 38125, 1110, 13]`. However, a joint tokenization of the entire string `"This is a fine day."` produces `[1212, 318, 257, 3734, 1110, 13]`, which better aligns with the model’s training data and intent.

Tokenization that communicates intent more effectively is crucial, as the model learns from the training text’s greedy tokenization. During training, the regularization of subwords is introduced to mitigate this issue. Subword regularization is a method wherein suboptimal tokenizations are deliberately introduced during training to enhance the model’s resilience. Consequently, the model encounters tokenizations that may not be the best greedy ones. While subword regularization effectively enhances the model’s ability to handle token boundaries, it doesn’t completely eliminate the model’s inclination toward the standard greedy tokenization.

Token healing prevents these tokenization discrepancies by strategically adjusting the generation process. It temporarily reverts the generation by one token before the prompt’s end and ensures that the first generated token maintains a prefix matching the last prompt token. This strategy allows the generated text to carry the token encoding that the model anticipates based on its training data, thus sidestepping any unusual encodings due to prompt boundaries. This is very useful when dealing with valid URL generation, as URL tokenization is particularly critical.

##### Acceleration

Acceleration significantly enhances the efficiency of inference procedures within a Guidance program. This strategy leverages a session state with the LLM inferencer, enabling the reutilization of key/value (KV) caches as the program unfolds. Adopting this approach obviates the need for the LLM to autonomously generate all structural tokens, resulting in improved speed compared to conventional methods.

KV caches play a pivotal role in this process. In the context of Guidance, they act as dynamic storage units that hold crucial information about the prompt and its structural components. Initially, GPT-style LLMs ingest clusters of prompt tokens and populate the KV cache, creating a representation of the prompt’s structure. This cache effectively serves as a contextual foundation for subsequent token generation.

As the Guidance program progresses, it intelligently leverages the stored information within the KV cache. Instead of solely relying on the LLM to generate each token from scratch, the program strategically uses the pre-existing information in the cache. This reutilization of cached data accelerates the token generation process, as generating tokens from the cache is considerably faster and more efficient than generating them anew.

Furthermore, the Guidance program’s template structure dynamically influences the probability distribution of subsequent tokens, ensuring that the generated output aligns optimally with the template and maintains coherent tokenization. This alignment between cached information, template structure, and token generation contributes to Guidance’s accelerated inference process.

![image](/api/v2/epubs/urn:orm:book:9780138280383/files/graphics/note.jpg) Note

This acceleration technique currently applies to locally controlled models in transformers, and it is enabled by default.

##### Structuring output and role-based chat

Guidance offers seamless support for chat-based interactions through specialized tags such as `{{#system}}`, `{{#user}}`, and `{{#assistant}}`. When using models like GPT-3.5-turbo or GPT-4, you can then structure conversations in a back-and-forth manner.

By incorporating these tags, you can define roles and responsibilities for the system, user, and assistant. A conversation can be set up to flow in this manner, with each participant’s input enclosed within the relevant tags.

Furthermore, you can use generation commands like `{{gen 'response'}}` within the assistant block to facilitate dynamic responses. While complex output structures within assistant blocks are not supported due to restrictions against partial completions, you can still structure the conversation outside the assistant block.

From the official documentation, here is an example of an expert chat:

[Click here to view code image](ch04_images.xhtml#f0126-01)

```
experts = guidance(
'''{{#system~}}
You are a helpful and terse assistant.
{{~/system}}
{{#user~}}
I want a response to the following question:
{{query}}
Name 3 world-class experts (past or present) who would be great at answering this?
Don't answer the question yet.
{{~/user}}
{{#assistant~}}
{{gen 'expert_names' temperature=0 max_tokens=300}}
{{~/assistant}}
{{#user~}}
Great, now please answer the question as if these experts had collaborated in writing a joint
anonymous answer.
{{~/user}}
{{#assistant~}}
{{gen 'answer' temperature=0 max_tokens=500}}
{{~/assistant}}''', llm=llm)
experts(query=' How can I be more productive? ')
```

The output conversation would look like the following:

[Click here to view code image](ch04_images.xhtml#f0126-02)

```
System
You are a helpful and terse assistant.

User
I want a response to the following question:
How can I be more productive?
Name 3 world-class experts (past or present) who would be great at answering this?
Don't answer the question yet.

Assistant
1. Tim Ferriss
2. David Allen
3. Stephen Covey

User
Great, now please answer the question as if these experts had collaborated in writing a joint
anonymous answer.

Assistant
To be more productive:
1. Prioritize tasks using the Eisenhower Matrix, focusing on important and urgent tasks first.
2. Implement the Pomodoro Technique, breaking work into focused intervals with short breaks.
3. Continuously improve time management and organization skills by following the principles of
David Allen's "Getting Things Done" method.
```

This approach with Guidance works quite well for one-shot chats (with a single message) or at most few-shot chats (with a few messages). However, because it lacks history building, using it for a comprehensive chat application becomes complex.

![image](/api/v2/epubs/urn:orm:book:9780138280383/files/graphics/note.jpg) Note

A more realistic chat scenario can be implemented by passing the conversation to the program and using a combination of `each`, `geneach`, and `await` tags to unroll messages, wait for the next message, and generate new responses.

##### Calling functions and building agents

To build a rudimentary agent in Guidance, you need to call external functions within a prompt. More generally, all core commands are functions from guidance.library.* and follow the same syntax, but you can also call out your own functions:

[Click here to view code image](ch04_images.xhtml#f0127-01)

```
def aggregate(best):
     return '\n'.join(['- ' + x for x in best])
program = guidance('''The best thing about the beach is{{gen 'best' n=3 temperature=0.7 max_
tokens=7 hidden=True}}
{{aggregate best}}''')
executed_program = program(aggregate=aggregate)
```

With this in mind, let’s compose a custom super basic agent, following the main idea behind the example from the development team here: *[https://github.com/guidance-ai/guidance/blob/main/notebooks/art_of_prompt_design/rag.ipynb](https://github.com/guidance-ai/guidance/blob/main/notebooks/art_of_prompt_design/rag.ipynb)*.

[Click here to view code image](ch04_images.xhtml#f0127-02)

```
prompt = guidance('''
{{#system~}}
You are a helpful assistant.
{{~/system}}

{{#user~}}
From now on, whenever your response depends on any factual information, please search the web by
using the function <search>query</search> before responding. I will then paste web results in,
and you can respond.
{{~/user}}

{{#assistant~}}
Ok, I will do that. Let's do a practice round
{{~/assistant}}

{{>practice_round}}

{{#user~}}
That was great, now let's do another one.
{{~/user}}

{{#assistant~}}
Ok, I'm ready.
{{~/assistant}}

{{#user~}}
{{user_query}}
{{~/user}}

{{#assistant~}}
{{gen "query" stop="</search>"}}{{#if (is_search query)}}</search>{{/if}}
{{~/assistant}}

{{#if (is_search query)}}
{{#user~}}
Search results:
{{#each (search query)}}
<result>
{{this.title}}
{{this.snippet}}
</result>
{{/each}}
{{~/user}}
{{/if}}

{{#assistant~}}
{{gen "answer"}}
{{~/assistant}}
'''
, llm=llm)

prompt = prompt(practice_round=practice_round, search=search, is_search=is_search)
query = "What is Microsoft's stock price right now?"
prompt(user_query=query)
```

The main parts of this structured prompt are as follows:

- **The actual search method and the `is_search bool` method** These tell the system whether a real search should be involved.
- **The “From now on, whenever your response depends on any factual information, please search the web by using the function <search>query</search> before responding. I will then paste web results in, and you can respond.” piece** This tells the model that not every user query needs to be searched on the web.
- **The `practice_round` variable** This acts as a one-shot example. It is crucial to determining the structure for the search function’s input, which is then generated with `{{gen "query" stop="</search>"}}` and saved in the `"query"` variable.
- **The `user_query` passed as a user message** This is used to generate the actual search query.
- **The logical control** This assesses whether there is a web search going on, and if so, appends the results.
- **The generation of a response** This generates an answer based on the query and search results, using the `gen` keyword.

Because you have become accustomed to SK planners and even more so to LangChain agents, this example with Guidance might seem quite rudimentary. You need to reconstruct the entire orchestration logic. However, it’s equally true that Guidance provides much greater control over the precise output structure. This enables you to create powerful agents even with smaller, locally hosted models compared to those of OpenAI.

### Summary

This chapter delved into language frameworks for optimizing AI applications. It addressed the need for these frameworks to bridge concepts like prompt templates, chains, and agents. Key considerations include memory management, data retrieval, and effective debugging.

The chapter introduced three major frameworks: LangChain, which handles models and agent optimization; Microsoft SK, with its versatile plug-ins and adaptable functions; and Microsoft Guidance, known for interleave generation, prompting, and logical control.

By exploring these frameworks, the chapter provided insights into enhancing AI capabilities through optimized structuring, memory utilization, and cross-framework integration.
