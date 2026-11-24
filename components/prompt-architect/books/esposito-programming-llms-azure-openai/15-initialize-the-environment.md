## Chapter 7

## Chat with your data

After exploring the use of Azure OpenAI APIs for a simple example that only involved prompt engineering, it’s time for a more complex use case. In this chapter, you will learn how to build a corporate chatbot that responds based on a document database that you will construct. Initially, this database will contain unstructured or semi-structured documents, but you will see how to extend the demo to use structured data in the last section of the chapter.

To achieve this, you will use an orchestrator to apply the RAG pattern, with the final section covering some of its possible extensions. You will construct the orchestrator using LangChain and will use Streamlit—a user-friendly web framework for developing what are commonly referred to as *data apps*—for the user interface. As usual, you will use GPT-3.5-turbo and GPT-4 via Azure OpenAI as the underlying model.

### Overview

The demo that you will develop in this chapter is a web application that helps employees access corporate documents and reports. The application, which will be protected by a layer of local authentication, will consist of a chat interface where users initiate conversations by asking questions. As mentioned, you will use LangChain to build an orchestrator and will experiment with RAG to enhance and contextualize the language model. In doing so, you will learn how creating a robust knowledge base can significantly enhance a solution’s performance.

#### Scope

Imagine that you work for a company with numerous documents and reports, some of which may lack proper tagging or classification. You want to create a platform to help your employees—particularly newcomers—gain a comprehensive understanding of the company’s knowledge-base onboarding. So, you want to develop an application to simplify the onboarding process and streamline document searches. This application will help employees navigate and explore the company’s extensive document repository through interactive conversations.

Here’s how the project unfolds (after you set up the knowledge base):

1. **User login** An employee logs in to the application.
2. **Engaging the language model** The user asks questions about the knowledge base, which triggers the RAG process. In this process:
  - The user’s queries are embedded.
  - The user’s queries are compared to the document chunks embedded in the vector store.
  - The most relevant documents are selected based on various criteria (like maximal marginal relevance or similarity).
  - These documents are passed to the LLM, along with the original user’s queries and a request to provide a comprehensive answer and precise references.
3. **Conversational phase** After the app’s initial response, the user can engage in a conversation about the knowledge base within the app.

You’ll harness the LLM at two key stages, using it for embeddings and to answer the user’s queries based on the retrieved context.

#### Tech stack

For this example, you will build a Streamlit (web) application that consists of two essential webpages: one for user login and the other for the chat interface.

You will use the Facebook AI Similarity Search (FAISS) library as the vector store because of its simplicity in persisting and adding/modifying existing chunks. However, in a production environment, it might be more reasonable to use a solution like Azure AI Search, which is already available in Azure and can be operated with service level agreements (SLAs) and security criteria.

You will use LangChain to construct the knowledge base. In this phase, you will mainly leverage simple APIs, particularly for the rewording of each document. You will break each document into chunks and, for each chunk, use an LLM to generate a series of questions and answers that resemble how you expect users to interact with these chunks. This improves matching in the search phase. Because users will predominantly interact with the knowledge base through questions, it makes sense to save the chunks in the vector store (also) in a question-answer format to increase the likelihood of semantic matching. This can also be beneficial for reducing the length of each chunk, resulting in lower token consumption and lower costs.

Note that even when LangChain is not used in production, it is still a common practice to use it for populating the knowledge base’s vector store, given the power and simplicity of the APIs it provides.

### What is Streamlit?

Streamlit is an open-source framework designed for data scientists and developers to easily create interactive data-driven applications using Python. Unlike other web-development frameworks like Django and Flask, Streamlit—launched in 2019 primarily to deploy Python apps, especially machine learning (ML) models, in minutes—streamlines the application-development process by eliminating (or at least hiding) the need to use HTML, CSS, and JavaScript.

#### A brief introduction to Streamlit

Streamlit is a Python-based framework designed to streamline the development of web applications, particularly applications for data analysis and visualization. It enables users to easily build interactive and data-centric web applications while staying within the familiar confines of Python. This reduces the need for front-end development skills (HTML, CSS, or JavaScript), at least in the proof-of-concept stage. The main goal of Streamlit is to allow data scientists and developers to focus on data and logic while still providing a nice interface for the application’s users.

The main motivation for using Streamlit stems from its simplicity and cost-effectiveness. In a way, Streamlit represents the best of both worlds between products like Tableau and Kibana and Python-based web frameworks such as Flask and Django. In fact, Streamlit combines the advantages of both Tableau and Kibana (which are data-visualization and analytics tools) and web frameworks like Flask and Django (which are used for building web applications in Python).

Streamlit simplifies the handling of data flow by executing the script from top to bottom every time there’s a code modification or user interaction. In other words, every time a user loads a web page built with Streamlit, under the hood, the entire script is executed. To optimize performance, Streamlit offers @st.cache decorators to efficiently manage functions that are resource-intensive in terms of execution time. The framework also makes it possible to build multipage applications integrated with an authentication layer through the session state manager.

The framework’s rich feature set includes a straightforward API for creating interactive applications with minimal code. It comes with prebuilt customizable components like charts and widgets. Furthermore, Streamlit has extended compatibility with various Python libraries such as scikit-learn, spaCy, and pandas, and data-visualization frameworks like Matplotlib and Altair.

#### Main UI features

After you install Streamlit using a simple `pip install streamlit` command, possibly in a virtual environment through venv or pipenv or anaconda, Streamlit provides a variety of user interface controls to facilitate development. These include the following:

- **Title, header, and subheader** Use the `st.title()`, `st.header()`, and `st.subheader()`functions to add a title, headers, and subheaders to define the application’s structure.
- **Text and Markdown** Use `st.text()` and `st.markdown()` to display text content or render Markdown.
- **Success, info, warning, error, and exception messages** Use `st.success()`, `st.info()`, `st.warning()`, `st.error()`, and `st.exception()` to communicate various messages.
- **Write function** Use `st.write()` to display various types of content, including code snippets and data.
- **Images** Use `st.image()` to display images within the application.
- **Checkboxes** Use `st.checkbox()` to add interactive checkboxes that return a Boolean value to allow for conditional content display.
- **Radio buttons** Use `st.radio()` to create radio buttons that enable users to choose from a set of options and to handle their selections.
- **Selection boxes and multiselect boxes** Use `st.selectbox() and st.multiselect()` to add these controls to provide options for single and multiple selections, respectively`.`
- **Button** Use `st.button()` to add buttons that trigger actions and display content when selected.
- **Text input boxes** Use `st.text_input()` to add text input boxes to collect user input and process it with associated actions.
- **File uploader** Use `st.file_uploader()` to collect the user’s file. This allows for single or multiple file uploads, with file type restrictions.
- **Slider** Use `st.slider()` to add sliders to enable users to select values within specified ranges. These can be used for setting parameters or options.

Streamlit also offers a range of data elements to enable users to quickly and interactively visualize and present data from various angles. These data elements include the following:

- **Dataframes** Use the `st.dataframe(my_data_frame)` command to display data as an interactive table. This feature enables users to explore and interact with data in the displayed dataset.
- **Data Editor** Use `st.data_editor(df, num_rows="dynamic")` to enable the Data Editor widget, which users can employ to interactively edit and manipulate data. This provides a convenient way to modify dataset content.
- **Column configuration** For dataframes and data editors, you can use commands like `st.column_config.NumberColumn("Price (in USD)", min_value=0, format="$%d")` to configure display and editing behavior. This offers you control over how data is presented and edited.
- **Static tables** Use `st.table(my_data_frame)` to display data in a clean, straightforward, tabular format.
- **Metrics** Use `st.metric("My metric", 42, 2)` to display metrics. Metrics are presented in bold font, with optional indicators of metric changes for better data comprehension.
- **Dicts and JSON** Use `st.json(my_dict)` to present objects or strings in neatly formatted JSON form. This makes complex data structures more accessible and comprehensible.

Finally, Streamlit offers a wide range of charting capabilities, with an API for streamlined data visualization. These include the following:

- **Built-in chart types** Streamlit provides several native chart types, which you access using functions like `st.area_chart`, `st.bar_chart`, `st.line_chart`, `st.scatter_chart`, and `st.map`. These built-in charts are integral to the framework, offering easy-to-use options to meet common data-visualization needs.
- **Matplotlib** Streamlit supports Matplotlib figures through the `st.pyplot(my_mpl_figure)` function. The powerful Matplotlib library enables you to create customized intricate charts.
- **External libraries** Streamlit supports external charting libraries like Altair, Vega-Lite, Plotly, Bokeh, PyDeck, and GraphViz to create custom, interactive, and specialized visualizations. These libraries (accessible via `st.altair_chart(), st.vega_lite_chart, st.ploty_chart`, and so on) offer a wide range of charting options to meet diverse data-visualization requirements.

With all these controls, Streamlit empowers developers to build user-friendly and interactive data applications that support a wide range of functionalities and user interactions and offers a comprehensive suite of tools to effectively present and explore data. [Figure 7-1](ch07.xhtml#ch07fig01) shows an example of a running Streamlit app containing a few controls.

![The figure is a screenshot presenting a sample web app with a sidebar on the left edge including a logo, a title and some link buttons. The body of the page consists of three panels containing a data table, an input form and a chart.](/api/v2/epubs/urn:orm:book:9780138280383/files/graphics/07fig01.jpg)

***FIGURE 7-1** A sample page built with Streamlit.*

#### Pros and cons in production

Although Streamlit offers remarkable advantages in terms of simplifying app development, it comes with certain limitations with respect to its use in production settings. For example:

- Streamlit is best suited for creating simple demo applications. If an application has a complex UI—for example, its state changes frequently, requiring a re-rendering of the entire scene each time—it may experience performance or latency issues.
- Streamlit limits your ability to customize the layout of the app because it does not support nesting containers, like columns.
- Although Streamlit provides functionalities like session state, caching, and widget callbacks, which facilitate the rapid creation of complex application flows, more intricate applications may encounter limitations stemming from the framework’s design.
- Customization can be difficult with Streamlit. Tailoring an app’s features and appearance often requires substantial effort, even necessitating the use of raw HTML or JavaScript code.
- Streamlit’s scalability in a production-ready environment is questionable. Therefore, it may not be the ideal choice for handling high traffic without the full complement of features offered by conventional web services.
- Although Streamlit provides interactive controls, achieving optimal performance may still require significant customization or even integration with external web components. This can offset its ease of use.

![image](/api/v2/epubs/urn:orm:book:9780138280383/files/graphics/note.jpg) Note

Streamlit supports external components through the `components` module. However, implementing an external component usually means writing a small ad-hoc web app with a more flexible web framework.

You should carefully consider Streamlit’s limitations as they relate to your business needs before implementing Streamlit (or any other framework) in a production environment. If you determine that these limitations pose an issue, you can always opt for a more robust alternative for production purposes. For instance, a Python web API developed using Flask, FastAPI, Django, or any other web framework, along with a dedicated front-end application, may be a more reliable solution.

### The project

Let’s get into the operational details. First, you will create two models on Azure—one for embeddings and one for generating text (specifically for chatting). Then, you will set up the project with its dependencies and its standard non-AI components via Streamlit. This includes setting up authentication and the application’s user interface. Finally, you will integrate the user interface with the LLM, working with the full RAG flow.

![image](/api/v2/epubs/urn:orm:book:9780138280383/files/graphics/note.jpg) Note

You could achieve a similar result in Azure OpenAI Studio (*[https://oai.azure.com/](https://oai.azure.com/)*) by using the Chat Playground, picking the Use My Data experimental feature, and then deploying it in a WebApp, which allows for some customization in terms of the WebApp’s appearance. However, this method is less versatile and lacks control over underlying processes such as data retrieval, document segmentation, prompt optimization, query rephrasing, and chat history storage.

#### Setting up the project and base UI

In this section, you will set up the project and the base UI using the source code provided. This section assumes you have already set up a chat model (such as Azure OpenAI GPT-3.5-turbo or GPT 4) in Azure, like you did in [Chapter 6](ch06.xhtml#ch06). It also assumes you have an embedding model—in this case, text-embedding-ada-002, available on Azure.

With the models ready, along with their keys, create a folder. Inside it, place a .py file that will contain the app code and create a subfolder with the documents you want to use. Then install the following dependencies via `pip` (or `pipenv` for virtual environments):

- `python-dotenv`
- `openai`
- `langchain`
- `docarray`
- `tiktoken`
- `pandas`
- `streamlit`
- `chromadb`

Next, set up an .env file with the usual key, endpoints, and model deployments ID, and import it:

[Click here to view code image](ch07_images.xhtml#f0187-01)

```
import os
import logic.data as data
import logic.interactions as interactions
import hmac
from dotenv import load_dotenv, find_dotenv
import streamlit as st
def init_env():
    _ = load_dotenv(find_dotenv())
    os.environ["LANGCHAIN_TRACING"] = "false"
    os.environ["OPENAI_API_TYPE"] = "azure"
    os.environ["OPENAI_API_VERSION"] = "2023-12-01-preview"
    os.environ["AZURE_OPENAI_ENDPOINT"] = os.getenv("AOAI_ENDPOINT")
    os.environ["AZURE_OPENAI_API_KEY"] = os.getenv("AOAI_KEY")

# Initialize the environment
init_env()
deployment_name=os.getenv("AOAI_DEPLOYMENTID")
embeddings_deployment_name=os.getenv("AOAI_EMBEDDINGS_DEPLOYMENTID")
```

Now you’re ready to use Streamlit to create the base UI and flow. Use the following code:

[Click here to view code image](ch07_images.xhtml#f0187-02)

```
st.set_page_config(page_title="Chapter 7", page_icon="robot_face")
def check_password():
    def password_entered():
        if hmac.compare_digest(st.session_state["password"], st.secrets["password"]):
            st.session_state["password_correct"] = True
            # No need to store the password
            del st.session_state["password"]
        else:
            st.session_state["password_correct"] = False

    # Return True if the password has been validated
    if st.session_state.get("password_correct", False):
        return True

    # Show input for password
    st.text_input(
        "Password", type="password", on_change=password_entered, key="password"
    )
    if "password_correct" in st.session_state:
        st.error("Password incorrect")
    return False

if not check_password():
    st.stop()  # Do not continue if check_password is not True.

# Authenticated execution of the app will follow
# Create a header in the Streamlit app for the AI assistant
st.header("Chapter 7 - Chat with Your Data")

# Initialize the chat message history if needed
if "messages" not in st.session_state.keys():
    st.session_state.messages = []

# Prompt for user input and save to chat history
if query := st.chat_input("Your question"):
    st.session_state.messages.append({"role": "user", "content": query})

# Display the prior chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.write(message["content"])

# If last message is not from assistant, generate a new response
if st.session_state.messages and st.session_state.messages[-1]["role"] != "assistant":
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            response = "" # here we will add the needed code to produce an LLM output
            # Display the AI-generated answer
            st.write(response)
            message = {"role": "assistant", "content": response}
            # Add response to message history
            st.session_state.messages.append(message)
```

[Figure 7-2](ch07.xhtml#ch07fig02) shows the result.

![The figure is a screenshot from a sample Streamlit application. It contains a header for the application title, a text input for the question and a button to send the question.](/api/v2/epubs/urn:orm:book:9780138280383/files/graphics/07fig02.jpg)

***FIGURE 7-2** The Streamlit chat application in action.*

![image](/api/v2/epubs/urn:orm:book:9780138280383/files/graphics/note.jpg) Note

This flow includes an authentication layer, which checks a unique password against a secret file (.streamlit/secrets.toml), which contains a single line:

```
password = "password"
```

#### Data preparation

Recall that the RAG pattern essentially consists of retrieval and reasoning steps (see [Figure 7-3](ch07.xhtml#ch07fig03)). To build the knowledge base, you will focus primarily on the retrieval part.

![The figure is a diagram made of one main horizontal section with two related blocks placed below. The horizontal section begins with a user icon and an arrow that connects to a block labeled Retrieval Step. The arrow is labeled Question. The Retrieval Step block connects to the block Reasoning Step over an arrow labeled Context and Facts. The Reasoning Step block connects to another user icon over an arrow labeled Final Answer. The Retrieval Step block links downward to a block titled Knowledge Base containing a Vector Store cylinder and two squares: API and DB. The Reasoning Step block links downward to a block titled Full Context containing three squares: Base Prompt, Chat History and Retrieved Docs.](/api/v2/epubs/urn:orm:book:9780138280383/files/graphics/07fig03.jpg)

***FIGURE 7-3** Diagram illustrating the building of a knowledge base.*

The knowledge base should encompass all the documents and data you want to make accessible and searchable, whether they are structured, unstructured, or semi-structured. However, there are certain considerations because the base RAG pattern relies primarily on a similarity search step, often of a semantic nature, which compares the user’s question with the data in the knowledge base.

One consideration relates to the size of documents in the database. You might need to break down large documents into smaller chunks due to the limited context size of LLMs. Fortunately, chunking documents works seamlessly with textual data. Because the user poses a question in textual form, and the data in your knowledge base is also in textual form, you can perform the comparison using embedded representations of the query and the original data stored as vectors in a vector store.

Another consideration relates to structured data, since the process differs. The user’s query must be transformed into a formal query, often in the form of an SQL query or an API call. This is fundamentally dissimilar from a similarity search; instead, it is a deterministic search.

Although you can construct a basic RAG application with a simple LLM chain by employing a retriever over a vector store of unstructured documents, the complete RAG pattern typically involves an agent equipped with various tools. These tools may include one to handle unstructured searches across a defined set of documents, one to make API calls to access diverse data sources, and even one to directly query an SQL database housing different data.

In this example, you will concentrate on using unstructured and semi-structured data, such as XML and JSON, to populate the knowledge base.

##### Vector store setup

To prepare for the retrieval phase, the first thing to do is set up a vector store. In this case, you will use Chroma, which is installed through `pip install chromadb`.

Chroma, licensed under Apache 2.0, has three run modes:

- In memory without persistence (useful for a single script or notebook)
- In memory with persistence on a local folder (this is the option you will use)
- In a docker container, on premises, or on the cloud

Like almost all vector stores, Chroma also stores original document contents and their metadata (which can be queried) along with embeddings. It supports `.add`, `.get`, `.update`, `.upsert`, `.delete`, and `.query` (which runs the similarity search) commands over multiple collections, which can be seen as the equivalent of tables. The default collection is `langchain`.

Once the documents are formed, you can easily initialize the vector store as follows:

[Click here to view code image](ch07_images.xhtml#f0190-01)

```
    db = Chroma.from_documents(docs,
                               AzureOpenAIEmbeddings(azure_deployment=embedding_deployment),
                               persist_directory="./chroma_db")
```

If you only wanted to perform a vanilla similarity (semantic) search, you would just run the following line:

[Click here to view code image](ch07_images.xhtml#f0191-01)

```
search_results = vectorstore.similarity_search(user_question)
```

However, for a real-world scenario, this is not enough. You need to work out the ingestion phase.

##### Data ingestion

In the simplest case, where documents are in an ”easy“ format—for example, in the form of frequently asked questions (FAQ)—and users are experts, there is no need for any document-preparation phase except for the chunking step. So, you can proceed as follows:

[Click here to view code image](ch07_images.xhtml#f0191-02)

```
# Define a function named load_data_index
def load_vectorstore(deployment):
    # specify the folder path
    path = 'Data'
    # create one DirectoryLoader for each file type
    pdf_loader = create_directory_loader('.pdf', path)
    pdf_documents = pdf_loader.load()
    xml_loader = create_directory_loader('.xml', path)
    xml_documents = xml_loader.load()
    #csv_loader = create_directory_loader('.csv', path)

    # chunking all documents, trying to split them until the chunks are small enough
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1500, chunk_overlap=200)
    docs = text_splitter.split_documents(pdf_documents)

    # load docs into Chroma DB
    db = Chroma.from_documents(docs,
                               AzureOpenAIEmbeddings(azure_deployment=deployment),
                               persist_directory="./chroma_db")

    # return the created database
    return db
```

As expected, this is far from reality. Documents are usually not in FAQ form, they can be very long, and their meaningful and relevant parts may be buried under hundreds of lines of useless information.

##### Rewording

To enhance retrieval capabilities, it is often advantageous to store multiple vectors for each document. The complexity arises primarily from how you generate these multiple vectors for a single document. Fortunately, there are ways to augment the original data generating multiple vectors per document. The most common techniques are as follows:

- **Smaller chunks** This involves dividing a document (or a big chunk of it) into smaller segments and embedding these smaller chunks but returning the original document at the retrieval step. In this way, the embeddings can capture the specific meaning for the semantic search step, but the whole context is returned for the reasoning part.
- **Summary** This means crafting a summary for each document and embedding it, either alongside the original document or as a replacement, so you can more accurately determine what a chunk is about.
- **Hypothetical questions** Here, you formulate hypothetical questions (like a FAQ document) that a document is well-suited to answer and embed these questions alongside or in place of the document. This approach also opens the door to manual embedding, allowing the explicit addition of queries or questions designed to lead to the retrieval of a specific document, and affording greater control.
- **Autotagging with metadata** With this, you automatically tag each document with the relevant metadata using another instance of an LLM.

A different approach to retrieval involves a contextual compression mechanism at runtime that compresses retrieved documents based on the query context. This mechanism returns only the pertinent information, compressing individual document content and filtering out unnecessary documents.

Implementing a couple of these techniques, the code would look like the following:

[Click here to view code image](ch07_images.xhtml#f0192-01)

```
    # specify the folder path
    path = 'Data'

    # create one DirectoryLoader for each file type
    pdf_loader = create_directory_loader('.pdf', path)
    pdf_documents = pdf_loader.load()

    # preparing the 'smaller chunks' strategy
    parent_splitter = RecursiveCharacterTextSplitter(chunk_size=4000, chunk_overlap=400)
    parent_docs = parent_splitter.split_documents(pdf_documents)
    child_splitter = RecursiveCharacterTextSplitter(chunk_size=400)

    # preparing the summary strategy
    summary_chain = (
        {"doc": lambda x: x.page_content}
        | ChatPromptTemplate.from_template("Summarize the following document:\n\n{doc}")
        | AzureChatOpenAI(max_retries=0, azure_deployment=deployment)
        # this step simply returns the first generation in the LLM result
        | StrOutputParser()
    )

    # file store for original full doc
    fs = LocalFileStore("./documents")
    store = create_kv_docstore(fs)

    # usual vector store for chunks
    vectorstore = Chroma(
        embedding_function=OpenAIEmbeddings(deployment=embedding_deployment),
        persist_directory="./chroma_db"
    )
    parent_id_key = "doc_id"
    retriever = MultiVectorRetriever(
        vectorstore=vectorstore,
        docstore=store,
        id_key=parent_id_key,
    )

# create document ids and add docs to the docstore
    parent_doc_ids = [str(uuid.uuid4()) for _ in parent_docs]
    retriever.docstore.mset(list(zip(parent_doc_ids, parent_docs)))

    # Adding smaller chunks
    smaller_chunks = []
    for i, doc in enumerate(parent_docs):
        _id = parent_doc_ids[i]
        # small chunks
        _sub_docs = child_splitter.split_documents([doc])
        for _doc in _sub_docs:
            _doc.metadata[parent_id_key] = _id
        smaller_chunks.extend(_sub_docs)
    retriever.vectorstore.add_documents(smaller_chunks)

    # Adding summaries
    summaries = summary_chain.batch(parent_docs, {"max_concurrency": 5})
    summary_docs = [Document(page_content=s,metadata={ parent_id_key: parent_doc_ids[i]})
for i, s in enumerate(summaries)]
    retriever.vectorstore.add_documents(summary_docs)
    # return the retriever
    return retriever
```

![image](/api/v2/epubs/urn:orm:book:9780138280383/files/graphics/note.jpg) Note

We are using LangChain Expression Language (LCEL) here for the summary chain.

With this code, you incorporate both smaller document segments and summaries into your system. If storage capacity allows, adding more documents is advantageous, particularly when using maximal marginal relevance (MMR) retrieval logic, which prioritizes diversity among documents closely related to the user’s query. Note that this code returns a retriever, whereas the earlier code snippet returned the underlying vector store.

![image](/api/v2/epubs/urn:orm:book:9780138280383/files/graphics/tip.jpg) Tip

One more aspect to consider for improving the full pipeline’s retrieval capabilities is the structure of the documents, since you may want to remove the table of contents (TOC), headers, or other redundant or misleading information.

#### LLM integration

When the document-ingestion phase is completed, you’re ready to integrate the LLM into your application workflow. This involves these key aspects:

- Taking into account the entire conversation, tracking its history with a memory object.
- Addressing the actual search query that you perform on the vector store through the retriever and the possibility that users may pose general or ”meta“ questions, such as ”How many questions have I asked so far?“ These can lead to misleading and useless searches in your knowledge base.
- Setting hyperparameters that can be adjusted to enhance results.

##### Managing history

In this section, you will rewrite the code for the base UI to include a proper response with the RAG pipeline in place:

[Click here to view code image](ch07_images.xhtml#f0194-01)

```
# If last message is not from assistant, generate a new response
if st.session_state.messages and st.session_state.messages[-1]["role"] != "assistant":
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            response = interactions.run_qa_chain(query=query, deployment=deployment_name,
retriever=retriever, chat_history=st.session_state.messages)

            # Display the AI-generated answer
            st.write(response)
            message = {"role": "assistant", "content": response}

            # Add response to message history
            st.session_state.messages.append(message)
```

Now rewrite the `run_qa_chain` method as follows:

[Click here to view code image](ch07_images.xhtml#f0194-02)

```
def run_qa_chain(query: str, deployment:str, retriever, chat_history=[]):
    # Create an AzureChatOpenAI object
    azureopenai = AzureChatOpenAI(deployment_name=deployment, temperature=0)

# Set up and populate memory
    memory = ConversationBufferMemory(memory_key="chat_history", return_messages=True)
    for message in chat_history:
        memory.chat_memory.add_message(message=BaseMessage(type=message["role"],
content=message["content"]))
    # Create a RetrievalQA object from a chain type
    retrieval_qa = ConversationalRetrievalChain.from_llm(
        # The language model to use for answering questions
        llm=azureopenai,
        # The type of chain (could be different for different use cases)
        chain_type="stuff",
        # The retriever to use for retrieving relevant documents
        retriever=retriever,
        # The memory, reconstructed at runtime
        memory = memory,
        # For logging
        verbose=False
    )
    # Run the question-answering process on the provided query
    result = retrieval_qa.run(query)
    # Return the result of the question-answering process
    return result
```

In this sample, it might have been simpler to keep everything together within the main Streamlit flow, eliminating the need to reconstruct the `ConversationBufferMemory` object and the entire retrieval chain with each query. However, real-world production scenarios often require a different approach. In such cases, you may need to integrate the interaction layer into a separate application and ensure segregation per user, which is naturally achieved here through Streamlit’s behavior: The script is rerun for each user, thus preserving user-specific histories.

##### LLM interaction

By simply putting together what you have done so far, you can start chatting with your data. (See [Figure 7-4](ch07.xhtml#ch07fig04).)

![The figure is a screenshot from a sample Streamlit application. It shows a conversation between the user and the LLM. The user asks what to do to get a reimbursement based on a previously loaded set of PDF files. The LLM replies at its best.](/api/v2/epubs/urn:orm:book:9780138280383/files/graphics/07fig04.jpg)

***FIGURE 7-4** Sample conversation with a chatbot about personal data.*

The core part of the interaction layer is as follows:

[Click here to view code image](ch07_images.xhtml#f0195-01)

```
    retrieval_qa = ConversationalRetrievalChain.from_llm(
        # The language model to use for answering questions
        llm=azureopenai,
        # The type of chain (could be different for different use cases)
        chain_type="stuff",
        # The retriever to use for retrieving relevant documents
        retriever=retriever,
        # The memory, reconstructed at runtime
        memory = memory,
        # For logging
        verbose=False
    )
```

Here, you make a couple of implicit choices: the chain itself and its type.

Choosing the type is simple. There are four options (discussed in [Chapter 4](ch04.xhtml#ch04)), and they all revolve around how the chain handles retrieved documents:

- **Stuff** This uses all documents together. It’s powerful but is subject to the ”lost in the middle“ prompt, where important information in the middle of the conversation is ignored.
- **Refine** This builds its answer by looping separately over documents and iteratively updating the response.
- **Map Reduce** This is first applied individually to each document (`Map`), and the results are then combined using a separate chain (`Reduce`).
- **Map Re-Rank** This applies an initial prompt for each document and assigns a confidence score to each response. The response with the highest score is then chosen and returned.

Regarding the chain type, here you used a `ConversationalRetrievalChain`. There are other ready-to-use options, however, such as `RetrievalQA` and `RetrievalQAWithSources`.

The key difference between existing ready-to-use RAG chains relates to how they handle the chat history. With `RetrievalQA`, the chat history remains static. It does not transform into a new query to be retrieved. In contrast, with `ConversationalRetrievalChain`, the chat history is merged with the latest user query using another LLM and a different customizable prompt (via `condense_question_prompt` and `condense_question_llm`) to create a new question for document retrieval.

Alternatively, you could build your own chain through LangChain Expression Language (LCEL), combining a system prompt with the conversation history and the retriever to be queried with the user’s query.

One more option, as outlined, is using an agent with retrieval tools. For this, there is a readymade API in LangChain: `create_conversational_retrieval_agent`.

##### Improving

To improve the results, you can alter several aspects of the code. For example:

- Modifying the query sent to the vector store
- Applying structured filtering to the result metadata
- Changing the selection algorithm used by the vector store to choose the results to send to the LLM (along with the quantity of these results)

`MultiQueryRetriever` generates variants of the input question to improve retrieval, using a similar prompt:

[Click here to view code image](ch07_images.xhtml#f0196-01)

```
You are an AI language model assistant. Your task is to generate five
    different versions of the given user question to retrieve relevant documents from a vector
    database. By generating multiple perspectives on the user question, your goal is to help
    the user overcome some of the limitations of the distance-based similarity search.
    Provide these alternative questions separated by new lines.
```

So, instead of the retriever used before, you can instantiate a `MultiQueryRetriever` and pass it to the `run_qa_chain` method, like so:

[Click here to view code image](ch07_images.xhtml#f0196-02)

```
enhanced_retriever = MultiQueryRetriever.from_llm(retriever=retriever, llm=azureopenai)
```

If you are using metadata (imported during the data-ingestion phase), you can use a `SelfQueryRetriever` to query over specific metadata in the following way:

[Click here to view code image](ch07_images.xhtml#f0197-01)

```
metadata_field_info=[
    AttributeInfo(
        name="author",
        description="The author of the document",
        type="string or list[string]",
    ),
    AttributeInfo(
        name="year",
        description="The year the document was written",
        type="integer",
    )
]
document_content_description = "Company instructions for…"
retriever = SelfQueryRetriever.from_llm(azureopenai, vectorstore, document_content_description,
metadata_field_info)
```

By design, you must instantiate `SelfQueryRetriever` directly on top of a vector store (not on top of another retriever), because it must query it directly to obtain relevant documents with respect to metadata. So, while you can instantiate a `MultiQueryRetriever` on top of a `MultiVectorRetriever`, this is not the case for a `SelfQueryRetriever`. However, you can assemble different retrievers using `MergerRetriever`, combining results from different retrievers and ranking the final list, possibly removing redundant results.

The selection algorithm behind the vector store’s `get_relevant_documents` method can be similarity or MMR. While similarity aims to obtain only the most similar documents, MMR selects the most diverse documents among the most similar retrieved documents. Currently, the `MultiVectorRetriever` class that you have been using to add custom mappings between stored embeddings and retrieved chunks doesn’t support MMR, but it is simple to rewrite it and extend its `_get_relevant_documents` inner method to add support for `vectorstore.max_marginal_relevance_search`.

One additional aspect to consider is the ability to engage with meta-questions, or questions that are not directly related to the user’s current query. The simplest scenario involves dealing with questions such as, ”What was the first question I asked?“ This can be managed effectively through a custom prompt, instructing the model to refer to the provided context only when necessary.

Addressing more complex inquiries, such as ”Are there any questions within the documents?“ is considerably more challenging. In the vast majority of cases, this type of question calls for a robust ReAct agent equipped with retriever tools and integrated text-analysis tools.

Based on practical experience, when combining multiple retrievers, using custom prompts, and possibly incorporating additional steps for anonymization and access control, it is often necessary to rebuild the RAG pipeline from scratch using the LangChain Expression Language (LCEL).

### Progressing further

What you’ve built so far addresses the initial scope of the project. However, in the real world, the introduction of a new and hot technology in a business domain just whets people’s appetites, and as a result, executives start asking for more.

The first direction to turn to progress this example further is to wonder whether RAG is the most appropriate approach or if a different philosophy—fine-tuning—would be a better fit. Second, there’s still a long list of extensions for making the solution richer and more effective.

#### Retrieval augmented generation versus fine-tuning

Fine-tuning involves customizing LLMs to harmonize with specific writing styles, domain expertise, or nuanced requirements. This can prove invaluable in applications for which responses must be finely tuned to cater to particular user preferences, tones, or terminologies. For example, it could be advantageous to fine-tune an LLM-driven customer-care assistant to imbue it with the company’s distinctive voice. However, fine-tuned models face a significant drawback: They maintain static representations of data at the time of training. If the underlying data undergoes changes or frequent updates, these models swiftly become obsolete, necessitating repetitive retraining, which entails increasingly longer times and costs for data preparation and the fine-tuning process itself. Moreover, the inner workings of fine-tuned models often remain opaque, akin to a black box, making it challenging to discern the rationale behind their responses.

In contrast, RAG systems are designed primarily for information retrieval. These systems excel at grounding their responses with evidence from external knowledge sources, reducing the risk of generating inaccurate or hallucinated information. RAG systems are particularly valuable in cases when obtaining detailed, reference-backed answers is essential. They also provide a high level of transparency, which results from the two-step nature of the RAG process: first retrieving relevant information from external documents or data sources and then using this information to generate a response. Users can inspect the retrieval component to understand which external sources were selected as relevant. However, RAG requires a big initial investment to build the database by merging and reorganizing existing data sources, and maintenance costs to keep the database up to date.

RAG is not particularly useful as a search engine because it relies on semantic search through embeddings and vector stores. Rather, its power lies in its ability to provide human-understandable responses to questions. Essentially, RAG simplifies the process of seeking information by encouraging users to ask questions instead of using conventional search queries. This reduces the common misuse of traditional search engines, transforming the process of finding answers into a more conversational experience.

The choice between fine-tuning and RAG depends on the specific requirements of an application. If detailed, reference-backed answers are vital, then RAG is the preferred choice. RAG is especially useful in scenarios where dynamic data sources require constant updates, since it can query external knowledge bases to ensure the information remains current. However, RAG systems may introduce slightly more latency than fine-tuned models, since they involve a retrieval step before generating a response.

The evolution of information-retrieval systems

For a short period after search engines first emerged in the 1990s, companies actively sought search engineers because the search engines of that era were not as advanced as they are today. Using the right keywords to locate a specific piece of information required a certain level of expertise—almost like an art form.

Information-retrieval systems have evolved over time, however. Now they deliver valuable search results even when users phrase their questions or queries incorrectly. We are now at a stage where we can not only provide relevant search results, but also offer definitive answers to questions (providing supporting materials and references).

Ironically, this development means companies may now need the skills of prompt engineers who can navigate the intricacies of the RAG pattern—that is, until LLM technology improves further, likely subjecting prompt engineers to the same fate as the search engineers of old.

Another important concern pertains to privacy. In the case of RAG, the process of storing and retrieving data from external databases is integral, which can be problematic when dealing with sensitive data. However, you can address this issue by implementing access control systems and permissions to regulate the retrieval of data, thus providing more precise control over the LLM’s access to sensitive information. In contrast, fine-tuned models may incorporate sensitive information, lacking a deterministic method to exclude such data when generating responses to questions.

Alternatively, you can consider a novel hybrid approach like Retrieval-Augmented Dual Instruction Tuning (RA-DIT) to improve reasoning capabilities. RA-DIT combines the strengths of fine-tuning and RAG for a more versatile solution. This process involves fine-tuning the LLM using the output from a RAG system as training data. This empowers the LLM to better comprehend the context specific to its use case. What sets RA-DIT apart is its incorporation of a human-in-the-loop approach, enabling a supervised learning process where responses can be carefully curated. When employing a retrieval step different from the typical commercial embedding models (such as OpenAI’s text-ada-002) and vector stores, RA-DIT is a useful approach for refining the retrieval step as well.

While RAG and fine-tuning are generally seen as opposites, there are many business use cases where they work well together. In the LLM-driven customer care assistant example, you would certainly need the RAG pattern to find information about products sold and fulfilled orders. However, as mentioned, you would also require fine-tuning to align with the company’s communication style.

Ultimately, the suitability of these approaches depends on various factors such as the need for domain-specific expertise, data dynamics, transparency, and user requirements. In summary, one of these methods is not universally superior to the other, and they’re not usually mutually exclusive.

#### Possible extensions

This example offers several potential extensions to transform the relatively simple application into a powerful company copilot. For example:

- **Source documents and follow-up questions** You can enrich the user experience by incorporating source documents and automatically generating follow-up questions, making interactions more informative and engaging.
- **LLamaIndex integration** For those seeking a specialized approach, using LLamaIndex instead of LangChain presents an opportunity to fine-tune document retrieval and optimize the RAG pipeline within the same Streamlit application.
- **Powerful search engine** Exploring more specialized vector stores and search engines, like Microsoft Cognitive Search, can significantly boost retrieval performance, bringing users more relevant information.
- **Different or additional storage layers** In cases where data exhibits high connectivity, has a complex semantic or formal structure, or is less unstructured, creating a knowledge graph—either in addition to or instead of a standard vector store—can prove highly advantageous. Both LangChain and LLamaIndex offer retrievers and chains compatible with various graph databases.
- **Security and privacy measures** To ensure data security and user privacy, you can integrate Microsoft Presidio and access control mechanisms, as briefly mentioned in [Chapter 5](ch05.xhtml#ch05).
- **Real-time evaluation and user feedback** To not just maintain but continuously improve system efficiency, real-time evaluation—facilitated through robust logging and tracing capabilities and user feedback mechanisms within the Streamlit app—can be invaluable.
- **Diverse data types** Expanding the system’s horizons by including various data types, such as content from YouTube, audio transcriptions, Word documents, HTML pages (also with LangChain’s `WebResearchRetriever`), and more, allows for a richer and more engaging knowledge base.
- **Structured data querying** Embracing structured data querying (like an SQL database) and amalgamating multiple tools within a single retrieval agent, possibly through a ReAct approach, broaden the scope of retrievable information.
- **Implementing functionalities** By linking the described RAG pipeline with the existing business logic through API calls within the LLM, the system gains the ability not only to retrieve information but also to execute actions.

![image](/api/v2/epubs/urn:orm:book:9780138280383/files/graphics/note.jpg) Note

These represent just a few potential extensions that not only enhance the RAG pipeline but also introduce features that cater to a wider range of user needs.

### Summary

In this chapter, you implemented the well-known RAG pattern to facilitate conversational navigation and querying of unstructured data. This chapter covered both the retrieval aspect (which is further divided into the preparatory and runtime querying phases) and the reasoning component (responsible for generating the user-visible response). Additionally, you explored various options for enhancing and extending the entire solution. The next chapter centers on building a conversational agent for service bookings using C# Semantic Kernel and MinimalAPI.
