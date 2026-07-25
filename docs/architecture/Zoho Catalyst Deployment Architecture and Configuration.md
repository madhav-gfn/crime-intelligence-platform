# **Technical Blueprint for Deploying Python Machine Learning, Social Network, and Graph Analytics Platforms on Zoho Catalyst**

## **Architectural Classifications of Zoho Catalyst and AppSail**

Zoho Catalyst represents an enterprise-grade serverless cloud platform engineered to streamline development through pre-configured backend utilities, secure managed databases, and highly scalable computing hosts1. Within this serverless ecosystem, AppSail operates as a robust Platform-as-a-Service (PaaS) engine1. It enables systems architects to build, host, and scale dynamic web services using contemporary programming stacks such as Java, Node.js, and Python1.  
Unlike traditional Function-as-a-Service (FaaS) environments that restrict code execution to highly coupled, template-driven serverless functions, AppSail provides independent execution spaces that are free from rigid coding conventions2. It is highly suited for deploying monolithic APIs, background processing workers, and interactive analytical visualization dashboards2. AppSail supports deployment through two main paradigms:

* **Catalyst-Managed Runtimes**: The platform provides native support for specific, pre-configured programming environments2. For Python-based systems, native runtimes include Python 3.10, 3.11, 3.12, and 3.135. In this mode, Catalyst handles the underlying execution platform, while the developer is responsible for bundling the application source files, libraries, and frameworks4.  
* **Custom Runtimes**: For applications requiring unsupported languages, specific system-level library dependencies, or precise operating system configurations, AppSail allows the deployment of Open Container Initiative (OCI)-compliant container images2. The platform supports loading images from external container registries—such as Docker Hub, Amazon Elastic Container Registry (ECR), or Google Artifact Registry—or directly uploading a local Docker archive2. These custom runtimes must be compiled for the Linux AMD64 (![][image1]) architecture2.

| Feature / Metric | Catalyst Serverless Functions | AppSail Services (Managed/Custom) |
| :---- | :---- | :---- |
| **Architecture** | Highly coupled, template-driven, event-based2 | Independent web services, flexible frameworks2 |
| **Deployment Mechanism** | Structured serverless packages4 | CLI upload, ZIP files, or OCI/Docker container images2 |
| **Execution Lifecycles** | Max 30 seconds for Basic/Advanced IO; 15 minutes for Cron8 | Continuous execution within standard container lifecycles4 |
| **Primary Billing Trigger** | Per-invocation metric and API calls4 | Active instance uptime and resource allocation4 |
| **Dependency Control** | Pre-engineered and managed by Zoho Catalyst4 | Entirely self-managed by the application developer4 |

## **Technical Profiles of the Specific Python Research Projects**

To deploy the specific python projects successfully, each system's library requirements, execution patterns, and processing bottlenecks must be evaluated against the limits of the AppSail container environment.

### **The IndiaCrimetrics Dashboard**

The IndiaCrimetrics project is an interactive Streamlit dashboard designed to perform regional crime pattern mapping, K-Means clustering, and Principal Component Analysis (PCA) on tabular incident datasets11. It relies heavily on standard PyData packages, including Pandas, NumPy, Scikit-learn, Plotly, and Matplotlib11.  
The mathematical underpinnings of the clustering process rely on the minimization of the squared Euclidean distances within ![][image2] clusters:  
![][image3]  
This objective function evaluates the spatial vectors ![][image4] representing incident coordinates, grouping them around calculated centroid means ![][image5]11. Because high-dimensional spatial datasets introduce computational complexity, PCA is applied to reduce dimensions while preserving variance11. Because this project is written in standard Python and utilizes mainstream machine learning frameworks, it aligns with a Catalyst-Managed Runtime2.  
However, running these operations dynamically inside an AppSail instance can quickly deplete memory during high-concurrency periods4. Streamlit maintains active WebSocket connections for every active user session, and running in-memory data cleaning on upload of large Excel files can lead to CPU spikes and memory exhaustion1.

### **The Langgraph\_AML\_Detection Framework**

The Langgraph\_AML\_Detection system is a state-based graph workflow designed for anti-money laundering transaction monitoring12. It coordinates a multi-factor compliance pipeline—such as Geographic Risk, Behavioral Analysis, Document Analysis, Crypto Risk, and Sanctions/PEP screening—governed by a shared state class (AMLState)12. This state-based orchestration manages real-time transaction objects and automates Suspicious Activity Report (SAR) generation using large language models (LLMs)12.  
When deployed, this system can run as an asynchronous web API using FastAPI or Flask within a Python 3.11 managed container2. However, because it relies on external API calls to LLM services (e.g., Groq, Claude) and external sanctions lists12, it requires strict environment variable management for API credentials and configurable risk thresholds12.

### **The criminal-network-visualization Engine**

The criminal-network-visualization tool is a specialized analyzer and visualizer designed for criminal social network analysis14. It performs transductive and inductive link predictions, community detection, social influence analysis, and graph mining on criminal actor network topologies14. Crucially, the system relies on the graph-tool library15.  
Unlike pure Python packages, graph-tool relies heavily on C++ system-level libraries, including Boost, CGAL, expat, and cairomm15. It must be compiled against these dependencies during installation15. Because developers cannot install system-level packages or execute custom C++ compilation steps in a standard Catalyst-Managed Runtime, this project cannot be deployed natively2.  
It must instead be deployed as a **Custom Runtime (Docker Container Image)** built on top of a Debian or Ubuntu base image with pre-compiled C++ system dependencies2.

### **The Opennyai Legal NLP Pipeline**

The Opennyai project is a natural language processing library designed to structure and summarize Indian legal documents16. It exposes three pre-trained deep learning models: Named Entity Recognition (NER) (e.g., en\_legal\_ner\_trf), Sentence Rhetorical Role classifier (SciBERT-HSLN baseline), and an Extractive Summarizer16.  
These models are based on transformer architectures (e.g., RoBERTa, SciBERT, and LLMs like Aalap-Mistral-7B)17. They require loading large deep learning model weights into RAM17.  
Attempting to run a standard pipeline execution of these models directly inside a managed AppSail instance will trigger Out-Of-Memory (OOM) errors, as the maximum memory allocation for an AppSail container is capped at 2048 MB19. To deploy this system on Zoho Catalyst, developers must split the architecture: the AppSail instance acts as a lightweight middleware, while the actual inference workload is offloaded to external GPU hosting platforms (e.g., Hugging Face Inference Endpoints) or routed to Catalyst's native Zia NLP APIs18.

## **Resource Optimization and Architectural Mitigation Strategies**

Deploying data-intensive and computationally heavy analytical pipelines on serverless container infrastructures requires specific architectural patterns to mitigate cold start latencies, manage memory limits, and handle startup timeouts4.

### **Cold Start and Timeout Mitigation**

AppSail employs a demand-driven instance lifecycle4. When the first request hits an idle or inactive application, the platform triggers a cold-start initialization to spin up a new container4.  
The application must start and bind to the dynamic container port inside a 10-second window4. If the startup script takes longer than 10 seconds—due to loading heavy machine learning models or imports—the container is terminated4. To prevent this, developers should use lazy-loading patterns to defer heavy model loading until after the port binding completes:

Python  
import os  
import sys  
import importlib  
import streamlit as st

\# Defer importing heavy libraries until after the server binds to the port  
def load\_ml\_pipeline():  
    if 'ml\_components' not in st.session\_state:  
        \# Programmatically import libraries after the initial page render  
        sklearn\_cluster \= importlib.import\_module("sklearn.cluster")  
        sklearn\_decomp \= importlib.import\_module("sklearn.decomposition")  
        st.session\_state\['ml\_components'\] \= {  
            'KMeans': sklearn\_cluster.KMeans,  
            'PCA': sklearn\_decomp.PCA  
        }  
    return st.session\_state\['ml\_components'\]

This pattern ensures the core script loads quickly, allowing the server to bind to the port in under 2 seconds4. The computationally intensive libraries are loaded asynchronously in the background.

### **Offloading Compute to Catalyst Serverless Components**

To keep the primary AppSail instance responsive within the 2048 MB RAM limit, developers should decouple long-running or memory-intensive jobs from the interactive presentation layer19. Rather than processing datasets directly inside the container, the dashboard can delegate workloads to other serverless components:

* **Interactive Presentation Layer**: AppSail hosts a lightweight web interface that handles user sessions and visualization rendering4.  
* **Ingestion and Background Processing Layer**: Long-running jobs (e.g., parsing raw logs, running K-Means/PCA, or calling LLM APIs for AML evaluation) are delegated to Catalyst Cron or Event functions, which support up to a 15-minute execution lifecycle8.  
* **Structured Data Tier**: Intermediate and processed results are written to the Catalyst Cloud Scale Data Store, allowing the dashboard to fetch pre-computed records in milliseconds20.

\+--------------------------------------------------------------+  
| User Interface (PaaS) | | AppSail Service | | \- Render Dashboard UI / Handle WebSockets | | \- Query Catalyst Data Store via Python SDK | \+------------------------------+-------------------------------+ | | Programmatic API Queries v \+------------------------------+-------------------------------+  
| Data & Storage Layer | | Catalyst Cloud Scale Data Store | | \- Relational Database Tables | | \- Pre-Computed Spatial Cluster Coordinates | | \- AML Transaction Records & SAR Statuses | \+------------------------------+-------------------------------+ ^  
| Structured Updates | \+------------------------------+-------------------------------+  
| Compute & Ingestion Layer | | Catalyst Cron / Event (FaaS) | | \- 15-Minute Execution Lifecycles | | \- Run K-Means, PCA, & Graph Analytics | | \- Execute LLM-Based Sanctions & PEP Queries | \+--------------------------------------------------------------+

### **Decoupling AML State and Large Language Model Pipelines**

For the Langgraph\_AML\_Detection system, orchestrating the multi-factor validation nodes requires managing transaction objects in a central, durable state12. Rather than storing the AMLState object in volatile local memory, the application should write transaction states directly to the Catalyst Cloud Scale Data Store20.  
The Python SDK can be used to query, update, and manage records in the Data Store dynamically20:

Python  
import os  
import zohocatalyst

\# Initialize Zoho Catalyst SDK  
def get\_catalyst\_app():  
    \# Catalyst injects credentials automatically into the AppSail runtime  
    return zohocatalyst.initialize()

def persist\_aml\_transaction(app, transaction\_data):  
    \# Obtain a reference to the relational Data Store  
    datastore \= app.datastore()  
    table \= datastore.table("AMLTransactions")  
      
    \# Construct a structured row dictionary matching the database schema  
    row\_record \= {  
        "TransactionID": transaction\_data\["id"\],  
        "Amount": transaction\_data\["amount"\],  
        "OriginCountry": transaction\_data\["origin\_country"\],  
        "DestinationCountry": transaction\_data\["destination\_country"\],  
        "RiskScore": transaction\_data.get("risk\_score", 0),  
        "Status": transaction\_data.get("status", "Pending")  
    }  
      
    \# Perform database write operation  
    inserted\_row \= table.insert\_row(row\_record)  
    return inserted\_row.get("ROWID")

def query\_high\_risk\_transactions(app):  
    datastore \= app.datastore()  
    \# Execute search query across indexed database columns  
    search\_config \= {  
        'search': 'High',  
        'search\_table\_columns': {  
            'AMLTransactions': \['Status'\]  
        }  
    }  
    search\_results \= app.search().execute\_search\_query(search\_config)  
    return search\_results

This structural shift protects the volatile container disk space, decouples the storage layer from the compute layer, and enables real-time data integration from other API gateways or ingest systems11.

## **The AppSail Managed Python Directory and Configuration Specification**

To deploy a Python-based application using the Catalyst CLI, the project root directory must contain the following file structure22:  
AnalyticsProject/ ├── .catalystrc \# Hidden configuration file containing portal and project mappings22 ├── catalyst.json \# Main project configuration file referencing the AppSail deployment target22 └── appsail-service/ \# Dedicated source directory housing the application code5 ├── app.py \# Main entry point for the Streamlit or FastAPI web service11 ├── requirements.txt \# Declared Python dependencies and package packages5 └── app-config.json \# Environment, startup command, memory, and port mapping settings5

### **Dependency Definition: requirements.txt**

To ensure the correct analytical and visualization libraries are compiled and installed during the AppSail deployment process, the developer must define the required dependencies in a requirements.txt file placed in the source directory5:  
streamlit\>=1.30.0 pandas\>=2.0.0 numpy\>=1.24.0 scikit-learn\>=1.2.0 plotly\>=5.15.0 zohocatalyst-sdk\>=1.0.0 langgraph\>=0.0.10 langchain-groq\>=0.0.1

### **AppSail Configuration Definition: app-config.json**

The app-config.json file is the primary configuration file used to define how Zoho Catalyst initializes, manages, and executes the container5. This file specifies runtime commands, sets memory limits, defines environment variables, and maps ports5.  
For Python applications like Streamlit, the configuration must dynamically bind the server to the environment variable X\_ZOHO\_CATALYST\_LISTEN\_PORT10.

JSON  
{  
  "command": "python3 \-m streamlit run app.py \--server.port $X\_ZOHO\_CATALYST\_LISTEN\_PORT \--server.address 0.0.0.0 \--server.headless true \--server.enableCORS false \--server.enableXsrfProtection false",  
  "buildPath": "./",  
  "stack": "python3.11",  
  "memory": 2048,  
  "env\_variables": {  
    "PROJECT\_ENVIRONMENT": "development",  
    "DATA\_STORE\_TABLE": "CrimeIncidents"  
  },  
  "scripts": {  
    "preserve": ""  
  }  
}

The configuration keys are defined as follows:

* **command**: The exact shell execution statement run by AppSail to start the server10. Streamlit must bind to the dynamic port passed via $X\_ZOHO\_CATALYST\_LISTEN\_PORT and listen on interface 0.0.0.010. The headless flag disables automated browser window opening in the headless serverless host environment.  
* **stack**: Specifies the managed runtime. This should target a supported runtime, such as python3.11 or python3.135.  
* **memory**: Allocates RAM resources. For heavy calculations, allocating the maximum tier of 2048 MB is recommended to prevent memory limit errors11.  
* **buildPath**: Specifies the relative directory location of the deployable build files5.

### **Project Association: catalyst.json**

The main catalyst.json file resides in the root directory and maps the local app folders to the remote Catalyst project configurations22:

JSON  
{  
  "appsail": {  
    "targets": \[  
      "appsail-service"  
    \]  
  }  
}

## **Standalone and Managed Deployment Workflows**

Once the directory structures are verified and the configuration files are defined, developers can deploy the application using either a Managed Runtime or a Custom Container Runtime.

### **Deploying via Catalyst-Managed Runtime**

To compile and deploy the source files to AppSail, navigate to the project root directory and execute the deploy command6:

Bash  
catalyst init

During this process, select the preferred portal, choose the target project, and confirm directory initialization22. When prompted for the AppSail setup, select **Catalyst-Managed Runtime**, choose the relative directory appsail-service, enter the service name, and confirm the Python programming stack24. This process validates the setup and updates both catalyst.json and the .catalystrc association files22.  
Once initialization is complete, deploy the AppSail service by executing6:

Bash  
catalyst deploy appsail

This command packages the application files in the specified build path, uploads them to the Catalyst remote container network, installs the defined Python libraries, configures the runtime environment, and starts the Streamlit server5.  
Once deployment is complete, the CLI outputs the unique, live application URL6. Developers can map a custom domain to this URL if needed2.

### **Standalone CLI Deployment**

For ad-hoc deployments where a local app-config.json is not defined, developers can use the AppSail standalone deployment options in the CLI6. This method bypasses the standard project initialization step, allowing developers to define configuration settings directly via CLI flags6. The command must be run from the root of a directory containing a valid catalyst.json file6:

Bash  
catalyst deploy appsail \\  
  \--name "StreamlitAnalytics" \\  
  \--build-path "/absolute/path/to/appsail-service" \\  
  \--stack "python3.11" \\  
  \--command "python3 \-m streamlit run app.py \--server.port \\$X\_ZOHO\_CATALYST\_LISTEN\_PORT \--server.address 0.0.0.0 \--server.headless true"

These parameters allow developers to configure the application name, specify the build path, define the runtime stack, and set the startup command dynamically6.

### **Deploying via Custom Container Runtime (OCI / Docker)**

For projects with complex system dependencies—such as criminal-network-visualization with its graph-tool dependency—developers should build and deploy a custom container image2.  
The Dockerfile must target the Linux AMD64 architecture2. It should install the required C++ dependencies, expose the container port, and define the startup entry point:

Dockerfile  
\# Use a secure Debian base image that supports graph-tool compilation  
FROM python:3.11\-slim-bookworm

\# Compile and install graph-tool's system-level dependencies  
RUN apt-get update && apt-get install \-y \--no-install-recommends \\  
    libboost-all-dev \\  
    libcgal-dev \\  
    expat \\  
    libsparsehash-dev \\  
    libcairomm-1.0-dev \\  
    build-essential \\  
    && rm \-rf /var/lib/apt/lists/\*

\# Install python dependencies  
WORKDIR /app  
COPY requirements.txt .  
RUN pip install \--no-cache-dir \-r requirements.txt

\# Copy source code files  
COPY . .

\# Expose default Catalyst container port  
EXPOSE 9000

\# Streamlit command using environment variable port binding  
ENTRYPOINT \["sh", "-c", "python3 \-m streamlit run app.py \--server.port $X\_ZOHO\_CATALYST\_LISTEN\_PORT \--server.address 0.0.0.0 \--server.headless true"\]

To deploy this container image, initialize or add the AppSail service using the CLI7:

Bash  
catalyst appsail:add

Select **Docker Image** when prompted for the runtime type7. Next, choose the preferred deployment protocol:

* **Docker Image Protocol**: Select Docker Image to choose an existing image built and tagged in the local Docker registry (e.g., docker://localhost/criminal-network:latest)7.  
* **Docker Archive Protocol**: Select Docker Archive and provide the absolute path to a exported tarball archive of the image (e.g., docker-archive:///absolute/path/to/image.tar)7. This archive can be generated locally using the docker save utility7.

After completing these steps, deploy the service using the standard CLI command6:

Bash  
catalyst deploy appsail

## **Operational Comparison Metrics**

To determine the most appropriate deployment strategy on Zoho Catalyst, developers should evaluate the specific compute, memory, and dependency requirements of each project.

| Project Core | Optimal Catalyst Deployment Stack | Recommended Memory Configuration | Dependency Constraints | External Integration Channels |
| :---- | :---- | :---- | :---- | :---- |
| **IndiaCrimetrics** \[cite: 11\] | Catalyst-Managed Python Runtime2 | 2048 MB19 | Standard Python packages (Pandas, Scikit-learn, Plotly)11 | Catalyst Cloud Scale Data Store for transaction caching20 |
| **Langgraph\_AML\_Detection** \[cite: 12\] | Catalyst-Managed Python Runtime2 | 1024 MB19 | State-based graph orchestration (LangGraph, OpenAI/Groq APIs)12 | Cloud Scale Data Store relational tables and external LLM endpoints12 |
| **criminal-network-visualization** \[cite: 14\] | Custom Container Runtime (Docker Image)2 | 2048 MB19 | Heavy C++ system dependencies (Boost, CGAL, graph-tool compilation)15 | Managed Docker registries (Docker Hub, AWS ECR, or GCP Artifact)2 |
| **Opennyai Pipeline** \[cite: 16\] | Managed Python Runtime (API Middleware)2 | 512 MB27 | Deep learning model size constraints17 | External GPU inference endpoints or native Catalyst Zia NLP APIs18 |

These deployment blueprints ensure that each analytical system is matched with the correct Zoho Catalyst runtime and resource configuration. This allows developers to build high-performance, cost-effective, and scalable cloud-native architectures that are optimized for complex data processing workloads4.

#### **Works cited**

> 1. Build, Host, Deploy, and Scale Apps Easily | Catalyst AppSail, [https://catalyst.zoho.com/app-sail.html](https://catalyst.zoho.com/app-sail.html)  
> 2. AppSail \- Catalyst Docs \- Zoho, [https://docs.catalyst.zoho.com/en/serverless/help/appsail/introduction/](https://docs.catalyst.zoho.com/en/serverless/help/appsail/introduction/)  
> 3. Execute Python SDK in AppSail \- Catalyst Docs, [https://docs.catalyst.zoho.com/en/sdk/python/v1/serverless/appsail/execute-appsail/](https://docs.catalyst.zoho.com/en/sdk/python/v1/serverless/appsail/execute-appsail/)  
> 4. AppSail Basics \- Catalyst Docs, [https://docs.catalyst.zoho.com/en/serverless/help/appsail/appsail-basics/](https://docs.catalyst.zoho.com/en/serverless/help/appsail/appsail-basics/)  
> 5. Catalyst-Managed Runtime, [https://docs.catalyst.zoho.com/en/serverless/help/appsail/catalyst-managed-runtimes/key-concepts/](https://docs.catalyst.zoho.com/en/serverless/help/appsail/catalyst-managed-runtimes/key-concepts/)  
> 6. Deploy AppSail \- Catalyst Docs, [https://docs.catalyst.zoho.com/en/cli/v1/deploy-resources/deploy-appsail/](https://docs.catalyst.zoho.com/en/cli/v1/deploy-resources/deploy-appsail/)  
> 7. Deploy AppSail as a Custom Runtime from the CLI \- Catalyst Docs, [https://docs.catalyst.zoho.com/en/serverless/help/appsail/custom-runtimes/deploy-from-cli/](https://docs.catalyst.zoho.com/en/serverless/help/appsail/custom-runtimes/deploy-from-cli/)  
> 8. Catalyst Functions and Timeout, [https://forums.catalyst.zoho.com/portal/en/kb/articles/catalyst-functions-and-timeout-10-11-2022](https://forums.catalyst.zoho.com/portal/en/kb/articles/catalyst-functions-and-timeout-10-11-2022)  
> 9. Catalyst Functions and Timeout, [https://forums.catalyst.zoho.com/portal/en/kb/articles/catalyst-functions-and-timeout](https://forums.catalyst.zoho.com/portal/en/kb/articles/catalyst-functions-and-timeout)  
> 10. AppSail Configurations \- Catalyst Docs, [https://docs.catalyst.zoho.com/en/serverless/help/appsail/appsail-configurations/](https://docs.catalyst.zoho.com/en/serverless/help/appsail/appsail-configurations/)  
> 11. JAY-ASHAR/IndianCrimetrics: Crime analytics dashboard using Python, Streamlit, K-Means clustering, PCA, and interactive visualizations to analyze crime trends across Indian states. \- GitHub, [https://github.com/JAY-ASHAR/IndianCrimetrics](https://github.com/JAY-ASHAR/IndianCrimetrics)  
> 12. AML Detection System using LangGraph \- GitHub, [https://github.com/subrata-samanta/Langgraph\_AML\_Detection](https://github.com/subrata-samanta/Langgraph_AML_Detection)  
> 13. sanctions-screening · GitHub Topics, [https://github.com/topics/sanctions-screening](https://github.com/topics/sanctions-screening)  
> 14. GitHub \- erichoang/criminal-network-visualization: This tool is a part of the paper "Inductive and Transductive Link Prediction for Criminal Network Analysis," published in the Journal of Computational Science in 2023\. It implements an analyzer and visualizer specialized for criminal (social) network analysis, including community detection, social influence analysis, and link prediction., [https://github.com/erichoang/criminal-network-visualization](https://github.com/erichoang/criminal-network-visualization)  
> 15. LouisWW/criminal\_network\_analysis: Analysing the resilience of criminal networks in an iterative fashion. \- GitHub, [https://github.com/LouisWW/criminal\_network\_analysis](https://github.com/LouisWW/criminal_network_analysis)  
> 16. Opennyai : An efficient NLP Pipeline for Indian Legal documents \- GitHub, [https://github.com/OpenNyAI/Opennyai](https://github.com/OpenNyAI/Opennyai)  
> 17. Legal-NLP-EkStep/rhetorical-role-baseline: OpenNyAI is a mission aimed at developing open source software and datasets to catalyze the creation of AI-powered solutions to improve access to justice in India. BUILD is the first benchmark dataset created by OpenNyAI · GitHub, [https://github.com/Legal-NLP-EkStep/rhetorical-role-baseline](https://github.com/Legal-NLP-EkStep/rhetorical-role-baseline)  
> 18. opennyaiorg (OpenNyAI) \- Hugging Face, [https://huggingface.co/opennyaiorg](https://huggingface.co/opennyaiorg)  
> 19. Deploy AppSail as a Catalyst-Managed Runtime from the Console, [https://docs.catalyst.zoho.com/en/serverless/help/appsail/catalyst-managed-runtimes/deploy-from-console/](https://docs.catalyst.zoho.com/en/serverless/help/appsail/catalyst-managed-runtimes/deploy-from-console/)  
> 20. Data Store \- Python SDK \- Catalyst Docs, [https://docs.catalyst.zoho.com/en/sdk/python/v1/cloud-scale/data-store/get-component-instance/](https://docs.catalyst.zoho.com/en/sdk/python/v1/cloud-scale/data-store/get-component-instance/)  
> 21. Catalyst Python SDK Integration in Third-Party Applications, [https://docs.catalyst.zoho.com/en/sdk/python/v1/integrate-sdk-in-third-party-apps/](https://docs.catalyst.zoho.com/en/sdk/python/v1/integrate-sdk-in-third-party-apps/)  
> 22. Initialize the Project \- Catalyst Docs \- Zoho, [https://docs.catalyst.zoho.com/en/tutorials/leadmanager-appsail/flask/init-project/](https://docs.catalyst.zoho.com/en/tutorials/leadmanager-appsail/flask/init-project/)  
> 23. Deploy Resources \- Catalyst Docs, [https://docs.catalyst.zoho.com/en/cli/v1/deploy-resources/introduction/](https://docs.catalyst.zoho.com/en/cli/v1/deploy-resources/introduction/)  
> 24. Initialize Your Catalyst Project \- Catalyst Docs, [https://docs.catalyst.zoho.com/en/tutorials/alien-city-appsail/python/initialize-project/](https://docs.catalyst.zoho.com/en/tutorials/alien-city-appsail/python/initialize-project/)  
> 25. Deploy AppSail as a Catalyst-Managed Runtime from the CLI, [https://docs.catalyst.zoho.com/en/serverless/help/appsail/catalyst-managed-runtimes/deploy-from-cli/](https://docs.catalyst.zoho.com/en/serverless/help/appsail/catalyst-managed-runtimes/deploy-from-cli/)  
> 26. Add an AppSail Service \- Catalyst Docs, [https://docs.catalyst.zoho.com/en/cli/v1/add-appsail/](https://docs.catalyst.zoho.com/en/cli/v1/add-appsail/)  
> 27. The Configuration Section \- Catalyst Docs \- Zoho, [https://docs.catalyst.zoho.com/en/serverless/help/appsail/console/configurations/](https://docs.catalyst.zoho.com/en/serverless/help/appsail/console/configurations/)

[image1]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAD8AAAAaCAYAAAAAPoRaAAADQElEQVR4Xu2XS6iNURTHl6RI3uQROpKJPKIQyqsoKc/IRIkMMDCRV5QYKJGBRyR1Ixkw8Sp5XTLByKOEvEJIGJAiiv+vtfc9+3zuOc53r4HB969f99tr7/OtvfZee337mhUqVKhQfWonJolu2Y6M2ovhgdaqjZggeofnWuovttjf55dLOJ0tXomj4e8F0TcdFLRXfBanA2Mru3Npqnho7vOBOGi+Ac0Je4N4IvpVdrVOk8VtMSS0O4gj4mbTCFdXcU0MCO3R4pLoGAfk0ELxUawwD2yn+CZmpYMSLTbv/6fBdxJXxX6rTDsc4ChqjPlkSfkoMmN60q5XLCyBzAht/M4X28wXOCsWZ5P5fHIFT3A9rRwY5wVbFLvG7v0QWxP7TPE8ae8Qv5J2a/RSPDM/w/WILClZzuDPmzt5K26I46H9Tqy18oKsEj/Ng+McDhX3xOrQHxeIfn73WHwSjaE/r/B1S4wXV8xrzDrz45ZVydx3zMS6gu8hJobnPuK+WC9GmheZR8GOSKvd5pOCD2KulRcnOib4jaKtlevCuDAmj3gP/i+a1xnmyYYctsqCx/MB882pO3gmtzxpx/PKy5j0FNEl6cc5qbhM7DM/AkyQCaE0+FTY07Nbr3hPNu03BPu50KaPrBgW2nUHn9VK+3PiUTghKygocafjJ4jfUODIEHYq+w5qBzYmnkf85q7oldjmBDvBMY895jse1aLgeVGD+JKxR7Ew7PrgjL1k/u3FUXrmU7U0eI7WddE5saXB45PFfiGeBngmI4HnEVZDTIz0Z3VZZV4WRUGLqcrEq63mZivbm6v2vBvbkoz9b2Kxsz5jdlIImTc3Pvojo8y/PsBztctQ0xlnNw+J7+KUeRZwWThr5c8dhZHLzGXRPdgQdYAVj6JWnBGDEhvvooim94N6xMJ/tfJRi5cnMq3UNKpSXKheByjaVUVgBNgodplfIN6YB3jCKoNEBMSn8L1YY37pYXz2tsWlhh3bLo6Zf+6q7kANEfBS89+fFHfM6w4Z2ZzikUhhg6uK1En/AaBw1fqHgPE4J4WnWeVNLhVOGbNIDEzsLOi8YK9FWuHJugXmX5+WLOJ/o5YEX6hQoUKFChXKp9/JI765dIuvfwAAAABJRU5ErkJggg==>

[image2]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAsAAAAcCAYAAAC3f0UFAAAA6ElEQVR4Xu2SvwtBURTHr0GR34NI/gmTwW6xmGWwyX/gPzDYZTbKbFFGZVFGhdFoUEpRfL/uubfXdd9O+dSn3j3n3HfPPe8p9dtU4AFeYM/JfZCHa3iGVSfnhcU7WHQTPk5wBqNuwscT9t1gGDdYD6wjKuSUNDzCsqx5yQ2cw5QpMjThANbgEMZhA65gNlD3hoVTOIJJibGFkq0QEnAB70qPr630m72wT/abg114hWMVcjlOgJMgvMwS7pVuoSMxC2f7kGdTvFX6F5jAmOTeR/Gr8esR0z83ZGBL4hb2ancLPKHgxP58Gy9d/CLxYfC8uQAAAABJRU5ErkJggg==>

[image3]: <data:image/png;base64,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>

[image4]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABIAAAAaCAYAAAC6nQw6AAABFElEQVR4XmNgGAWjgPqAF4hFgJgRyheEipEEtgLxPSB+DsSHgVgHyn8BxCUMCMPxAmEgtoayJYD4MhB/BWJ9IL4BxDeh4ngBMxAnI/FNgfgtEK8BYk4gdgBifiR5EABZkA/ErGjiKCATiP8DcTG6BBKYC8Q7GfCEHygcFgDxZyC2Q5UiDoBMBnlRFIgvMqCGiRYQu0HZeAEsTJSBeCYQ/2SAhA/I/xFAvJkB4YUmIFZggFjkDRWDA5AikOL9QNwDxEFA/AwqthyIhRBKGYyAOIoB4mqssQjyFijxwQAHEEsh8WEA5EqQ4VMZiExXuAAovO4wQCJClQHVtSQBUNI4CcQyQNwKxAKo0qQBUJiCvD4KBgoAAMxiJhYQI0BiAAAAAElFTkSuQmCC>

[image5]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABQAAAAaCAYAAAC3g3x9AAABOElEQVR4Xu2SrUtDYRTGH8OYIMMZRBlrNpvBJNgUbAaDxWjwP1jQ7F8gGGcUBEHX/EAwGU0iiMGqsxg0DPR5PPfdzt6L7l4tG+wHv3Cfw30/znuAIUP6jwItx+Ff0UJX9J5Ou3w2yXIzR5/pGR1zeY1+uu/M1OkHXXZZlT7SG5d5lugGHYkL4pY+0RmXaXFtUndZYJxe031Y71O80QYdddku7Lo6RW7047b7LtFL2qTzsEWLrv4r6pUW3EOnHxe0BVtU11tLctX1UHr9O9hmKdSr98RTekgXYBu80HN0+jRBV+gqbJx0mBTacQvWvwqdcjUt4L8D6m/c828UqLAYF3qgefU9bxNmbTIu9OAB3TPbZp2+xmEGjvDD/GVFr7tDD2C32uwu50e9Poa9+An+ebpAmAIN/YDyBayHMbVFk6cFAAAAAElFTkSuQmCC>