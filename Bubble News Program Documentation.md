# **BUBBLE NEWS Version 0.1 Beta: System Architecture and Implementation Specifications**

## **Executive Summary and Architectural Philosophy**

BUBBLE NEWS Version 0.1 Beta represents a highly specialized, command-line-based news aggregation and summarization engine designed for personal deployment on the Windows 10 operating system1. The software addresses the contemporary challenge of information saturation by autonomously aggregating Really Simple Syndication (RSS) feeds, identifying semantically related articles, extracting core facts, and synthesizing them into a consolidated, highly readable daily digest1. Designed for users with foundational coding knowledge, the application operates entirely without a graphical user interface, relying instead on terminal execution and operating system-level task scheduling to perform its duties invisibly in the background2.  
The foundational architectural principle driving BUBBLE NEWS is the rigid delineation of responsibilities between deterministic script execution and probabilistic artificial intelligence processing1. The architecture dictates that Python is strictly responsible for all mechanical operations, which include network requests, feed parsing, chronological filtering, HyperText Markup Language (HTML) parsing, operating system integration, and Simple Mail Transfer Protocol (SMTP) transmission1. Conversely, the Google Gemini Large Language Model (LLM) is exclusively tasked with intellectual operations, which encompass duplicate detection, event clustering, content summarization, factual extraction, and categorical reassignment1. By enforcing this separation, the system ensures that the AI is not burdened with basic web scraping protocols, while simultaneously restricting the LLM from inventing external Uniform Resource Locators (URLs), fabricating journalistic sources, or hallucinating synthetic images1. The culmination of this pipeline is a single, cleanly formatted HTML email delivered securely to the user's inbox2.

## **Core Component Topology and File Structure**

To maintain a minimal footprint while ensuring security and extensibility, the application is divided into five core operational files, supplemented by necessary environment and dependency configurations2. The system enforces a strict boundary between public configuration parameters, which may be safely committed to version control systems like GitHub, and private cryptographic secrets, which must remain isolated on the local execution environment1.  
The following table delineates the required file topology for the BUBBLE NEWS deployment:

| Filename | Component Classification | Primary Responsibility and Scope |
| :---- | :---- | :---- |
| bubble\_news.json | Public Configuration | Stores the user's customized taxonomy of RSS feeds organized by distinct categorical arrays. |
| config.py | Core Configuration | Central configuration declaring email credentials, AI model keys, execution schedule, and application settings with safe generic placeholders. |
| bubble\_news.py | Core Application | The primary Python executable coordinating the mechanical extraction pipeline and the intellectual synthesis pipeline. |
| run\_bubble\_news.py | Runner | The direct execution entry point called manually or triggered by Windows Task Scheduler. |
| .gitignore | Version Control | Instructs the Git daemon to exclude private files, logs, and generated previews, preventing accidental exposure on public repositories. |
| requirements.txt | Dependency Management | Catalogs the external Python libraries required for the system, ensuring standardized and reproducible execution environments. |

### **Data Flow and Pipeline Execution**

The system follows a strict, sequential pipeline during execution to guarantee data integrity from ingestion to transmission. The application first initializes by loading the public categorical structures from the JSON file and the core credentials from `config.py` (or local environment variables). The mechanical pipeline then iterates through all configured RSS endpoints, downloading syndication XML data and applying a chronological filter to isolate entries published strictly within the preceding twelve hours.  
For every article satisfying the temporal constraint, Python initiates direct HTTP requests to the source URLs, utilizing advanced scraping libraries to extract the raw journalistic text, author attributions, and relevant featured images while stripping away advertising boilerplate. This sanitized, structured dataset is then transmitted via API to Google Gemini. The LLM analyzes the dataset, identifying semantic correlations to merge duplicate reporting into consolidated narratives, and formats the output into strict JavaScript Object Notation (JSON). Python subsequently parses this AI-generated JSON, mapping the data into a responsive, inline-styled HTML email template. The final stage routes this generated digest through a secure, encrypted SMTP connection, delivering the payload to the configured user.

## **Configuration, Taxonomy, and Cryptographic Security**

Because the prototype is designed for personal deployment but explicitly engineered with the expectation that the source code may be hosted on public repositories, the architecture mandates robust security regarding user credentials.

### **The JSON Taxonomic Structure**

The informational taxonomy is entirely user-defined. The system relies on the `bubble_news.json` file, which serves as a public-facing configuration document where primary keys represent broad news categories (e.g., "Technology", "World", "Science") and values are arrays containing the target RSS feed URLs. The system is strictly forbidden from autonomously redefining or restructuring the user's overarching categorical definitions. While the AI is permitted to analyze a consolidated story and transition it from its inherited source category to a more semantically accurate category, it must only utilize the categories explicitly declared within the JSON file, expressly avoiding the spontaneous generation of arbitrary buckets such as "Trending" or "Miscellaneous". The JSON schema is validated during initialization to ensure all URLs are properly formatted strings and that all structural constraints are met.

### **Centralized Core Configuration (`config.py`)**

Hardcoding sensitive real credentials—such as your real Google Gemini API key or Disroot SMTP password—directly into public repositories constitutes a critical security vulnerability. To prevent this, the project establishes a centralized `config.py` file using safe generic placeholders (`"YOUR_GEMINI_API_KEY"`, `"YOUR_EMAIL_PASSWORD"`, `"your-email@example.com"`). Developers can customize `config.py` locally or supply environment variables without altering the core codebase.

## **Network Aggregation and Chronological Filtering**

The mechanical pipeline initiates the data ingestion phase, utilizing Python to parse diverse syndication protocols and filter content against strict temporal constraints.

### **Managing The Twelve-Hour Operational Window**

The central operational constraint of the aggregator is its twelve-hour news window. Upon execution, the application captures the current system time and calculates a definitive cutoff timestamp exactly twelve hours prior1. The Python application iterates through the JSON categorical arrays, connecting to each configured RSS endpoint via the standard feedparser library1. If a feed contains no articles published within this highly specific window, the system simply bypasses the feed; an empty temporal window is considered a normal operational state and must never trigger a fatal exception1.  
A significant technical hurdle in RSS aggregation is the chaotic historical landscape of syndication date formatting. Various iterations of syndication technologies enforce conflicting date standards. For instance, the original CDF standard mandated ISO 8601:1988 formatting, while RSS 0.91 and RSS 2.0 mandated the Date and Time Specification of RFC 82215. RFC 822 famously enforces two-digit or four-digit years accompanied by character-based timezone abbreviations (e.g., Thu, 01 Jan 2004 19:48:21 GMT)15. Conversely, RSS 1.0 and Atom 1.0 mandate W3CDTF or strict RFC 3339 representations, requiring specific separators and numeric timezone offsets (e.g., 2003-12-31T10:14:55-08:00)15.  
Attempting to parse this erratic data using Python's standard datetime.strptime function is highly inefficient, as it requires the developer to anticipate and manually define every possible string format via specific regex-like directives17. Furthermore, standard parsers frequently fail when confronting timezone ambiguities or malformed character encodings19.

### **Standardizing Time with python-dateutil**

To resolve these chronological inconsistencies, the system integrates the python-dateutil library, specifically leveraging its highly resilient parser module17. The dateutil.parser.parse() function utilizes a sophisticated heuristic algorithm capable of automatically detecting and interpreting dozens of disparate date string formats without requiring explicit pattern declarations15.  
The following table demonstrates the vast array of formats the dateutil parser successfully normalizes for the application:

| Format Standard | Example String Input | Python Datetime Resolution Capabilities |
| :---- | :---- | :---- |
| RFC 822 (Standard) | Thu, 01 Jan 04 19:48:21 GMT | Resolves standard syndication timestamps including timezone abbreviations15. |
| W3CDTF (Numeric TZ) | 2003-12-31T10:14:55-08:00 | Accurately calculates UTC offsets from numeric timezone declarations15. |
| ISO 8601 (Strict) | 20031231 or 2003-12-31 | Parses both compressed and hyphenated ISO structures seamlessly15. |
| Ambiguous / Fuzzy | 5th January 2025 | Extracts valid datetime objects by ignoring surrounding text when fuzzy=True is enabled17. |

For strict ISO 8601 strings (frequently encountered in Atom feeds), the system may optimize performance by utilizing the dateutil.parser.isoparse function, which bypasses the heavier heuristic logic in favor of rapid, targeted extraction16. By leveraging these tools, Python normalizes all incoming timestamps against the user's localized execution time, ensuring that only articles published within the preceding twelve hours are permitted into the extraction pipeline1.

## **Advanced Content and Metadata Extraction**

RSS feeds historically truncate article content to minimize bandwidth, often providing only a headline, a brief description, and a hyperlink1. To provide the LLM with sufficient context for intellectual synthesis, the Python pipeline must autonomously visit the source URL of every valid article to extract the complete journalistic text1.  
The application relies on newspaper3k, an advanced Python library specifically engineered for news scraping, full-text extraction, and article metadata curation14. Because news websites are notoriously cluttered with dynamic Document Object Model (DOM) elements, executing a raw HTML parser would result in the ingestion of extraneous navigation menus, cookie consent banners, localized advertisements, and algorithmic recommendations1. The newspaper3k library circumvents this by utilizing advanced Natural Language Processing (NLP) heuristics to identify the central text node of a webpage, systematically discarding unrelated boilerplate and social media widgets1.  
During this traversal, the pipeline also extracts visual metadata. The system is instructed to locate the primary featured image of the article, prioritizing Open Graph (og:image) tags and high-resolution header images1. These images are captured and temporarily stored for later injection into the final email template1. Crucially, the architectural specification expressly forbids the AI from synthesizing generative imagery; all visual media must be directly sourced from the original journalistic publications to maintain the factual integrity of the newsletter1.  
If the newspaper3k extraction fails—often due to stringent paywalls, aggressive anti-bot captchas, or timeout constraints—the system exhibits fault tolerance by catching the exception, logging a warning to the console, and gracefully falling back to the truncated summary provided by the initial RSS feed1.

## **Intellectual Synthesis via Google Gemini**

With a sanitized, chronological dataset of full-text articles assembled, the mechanical pipeline hands execution over to the intellectual engine1. The Google Gemini LLM is tasked with analyzing the corpus, reducing noise, and synthesizing narratives1.

### **Semantic Deduplication and Consolidation**

The paramount feature of BUBBLE NEWS is its capacity to resolve overlapping coverage1. Major global events are simultaneously covered by numerous competing agencies (e.g., Reuters, Associated Press, BBC)1. Presenting these as distinct articles would overwhelm the user and violate the core purpose of a summary application2.  
Through an extensively engineered internal prompt, Gemini is directed to analyze the textual dataset and identify semantic equivalencies across articles1. The model clusters highly correlated stories representing the same underlying event1. The prompt then directs the model to consolidate these clusters into a singular, unified narrative1.  
The LLM is governed by strict factual constraints: it must distill the foundational queries of journalism (what occurred, who is involved, the location, the timeline, and the macro-level implications) while strictly avoiding the hallucination of facts, the fabrication of quotes, or the invention of journalistic sources1. When sources provide disparate details—such as one agency reporting a specific casualty metric while another provides an exclusive government statement—the AI must intelligently fuse these non-repetitive data points into the overarching summary, thereby generating a narrative that is inherently more comprehensive than any individual source1. To maintain attribution, the AI must append a list of all contributing publishers to the conclusion of the consolidated story (e.g., "Sources: Reuters · BBC · AP")1.

### **Categorical Organization**

Following deduplication, the LLM analyzes the resulting narratives to determine their optimal placement within the user's defined JSON taxonomy1. While articles initially inherit the category associated with their originating RSS feed, the AI possesses the authority to dynamically reassign an article to a different category if the semantic content aligns more accurately with an alternative structural bucket1. The prompt explicitly restricts the AI from deviating from the provided JSON keys, ensuring the output aligns perfectly with the user's expectations1.

### **Enforcing Strict JSON Schema Output**

A critical failure point in LLM integrations occurs when the model returns unstructured text, conversational filler, or arbitrary HTML syntax that breaks downstream processing scripts1. To ensure a seamless handoff back to the Python mechanical pipeline, the system utilizes controlled generation techniques provided by the Google Generative AI Application Programming Interface (API)7.  
By explicitly defining the response\_mime\_type parameter as application/json, the system forces the Gemini model to abandon conversational outputs in favor of programmatic data structures7. Furthermore, the API request includes a predefined response\_schema object7. This schema acts as a strict blueprint, dictating that the output must consist of an array of categories, which internally house arrays of stories, which in turn contain specific string fields for the title, summary, source lists, and image URLs1. This architectural enforcement guarantees predictable, type-safe data that the Python application can instantly parse and map into internal dictionaries without requiring complex, error-prone regular expression extraction1. If the API request times out or the model hallucinates outside the schema, the Python script traps the error and halts execution to prevent the delivery of a corrupted digest1.

## **Email Presentation and Transmission Protocol**

The final phase of execution entails transforming the AI-generated JSON into a visual presentation and transmitting it securely over the internet1.

### **Inline Cascading Style Sheets and MIME Structure**

The email must present a clean, highly legible, and professional news-oriented layout utilizing sans-serif typography1. Designing HTML for email clients is notoriously difficult, as major email providers routinely strip \<style\> blocks in the \<head\> of the document and ignore externally linked Cascading Style Sheets (CSS) to prevent malicious code execution29. Consequently, the Python script must dynamically generate HTML utilizing extensive inline CSS attributes directly applied to the HTML tags29.  
To construct the email payload, the application utilizes the email.mime module30. The script generates a MIMEMultipart base object, which acts as a container supporting multiple distinct parts32. The Python pipeline injects a MIMEText object representing the raw HTML content, ensuring that the final transmission is correctly recognized by email clients as an HTML rendering rather than a plaintext string30.  
The visual layout groups the synthesized stories beneath distinct categorical headers1. The system intelligently integrates the extracted images, limiting the visual media to one to three images per category to prevent aesthetic bloat and excessive bandwidth consumption1. Crucially, the bottom of every category block contains an explicitly defined "Article Links" section, presenting the user with clickable hyperlinks directing them to the original source journalism, thereby ensuring total transparency regarding the AI's synthesis1.

### **Secure SMTP Transmission via Disroot**

The transmission relies on the Python smtplib module to interact with the designated Disroot mail servers (disroot.org)1. To maximize user privacy, the architecture circumvents external distribution lists; the authenticated user's email address serves simultaneously as the sender and the recipient, effectively executing a closed-loop delivery2.  
The architecture specifies the use of Port 5871. Understanding this choice requires examining the historical evolution of email transmission. Initially, Port 25 was universally utilized for SMTP relay and client submission; however, due to rampant exploitation by botnets transmitting spam, most internet service providers and hosting environments aggressively block outbound traffic on Port 2534. Port 465 was subsequently introduced for Implicit TLS (SMTPS), meaning the connection expects cryptographic encryption from the very first byte35. However, the Internet Engineering Task Force (IETF) formally standardized Port 587 (via RFC 6409\) as the default port for authenticated message submission using the STARTTLS protocol34.  
The BUBBLE NEWS application adheres strictly to this modern standard, executing the following programmatic handshake to secure the payload:

> 1. smtplib.SMTP("disroot.org", 587): The Python script establishes an initial, plaintext Transmission Control Protocol (TCP) connection to the Disroot server1.  
> 2. smtp.ehlo(): The client issues an Extended Hello command, identifying itself and requesting the server's supported cryptographic capabilities33.  
> 3. smtp.starttls(): Recognizing the server's capabilities, the script issues the STARTTLS command. This critical phase upgrades the existing plaintext connection into a fully encrypted Transport Layer Security (TLS) tunnel, protecting all subsequent commands from man-in-the-middle interception33.  
> 4. smtp.login(): Within the encrypted tunnel, the script safely transmits the credentials retrieved from the hidden .env file to authenticate the session33.  
> 5. smtp.sendmail(): The MIMEMultipart payload is transmitted securely to the server33.  
> 6. smtp.quit(): The connection is safely terminated33.

The application contains rigorous error handling surrounding this sequence. If the server lacks a valid SSL certificate (e.g., an incorrect Common Name configuration), or if a local firewall blocks Port 587, the smtplib protocol will raise an exception36. The system traps this error, logging the failure without erroneously claiming the email was successfully delivered1.  
The following table summarizes the SMTP port specifications evaluated during architectural development, reinforcing the selection of Port 587:

| Port | Protocol Standard | Cryptographic Mechanism | Implementation Rationale |
| :---- | :---- | :---- | :---- |
| 25 | Standard Relay | Plaintext (STARTTLS Optional) | Rejected due to universal blocking by residential ISPs to prevent spam35. |
| 465 | SMTPS (Implicit) | Implicit TLS | Historically deprecated by IETF; requires encryption before SMTP commands are issued35. |
| 587 | Client Submission | STARTTLS Upgrade | The IETF standard for authenticated client submission. Widely supported and highly secure34. |
| 2525 | Unofficial Fallback | STARTTLS Upgrade | Not endorsed by IETF; utilized only when restrictive networks aggressively block Port 58735. |

## **Operating System Integration and Execution Scheduling**

While the application supports manual execution via the run\_bubble\_news.py script, its primary utility is realized through automated, background scheduling1. Version 0.1 Beta integrates directly with the native Windows Task Scheduler to achieve this autonomy without relying on heavy background daemon loops that consume active memory1.  
Rather than forcing the user to navigate the graphical Windows interface, the schedule\_bubble\_news.py script utilizes the Python subprocess module to interface directly with the command-line utility schtasks.exe42. The subprocess.run() function allows Python to spawn a new operating system process, execute the required arguments, and capture the execution output for logging43.  
To register a daily execution, the script dynamically resolves the absolute file paths to both the Python binary (python.exe) and the bubble\_news.py file to prevent path resolution errors stemming from relative execution directories45. The script then constructs an argument list to execute the task creation.  
The programmatic command issued to the operating system resembles the following parameter structure: schtasks /create /tn "BubbleNews" /tr "C:\\Path\\To\\python.exe C:\\Path\\To\\bubble\_news.py" /sc daily /st 08:0042.  
The table below defines the arguments manipulated by the Python subprocess to interact with schtasks.exe:

| Argument Flag | Description and Functionality |
| :---- | :---- |
| /create | Directs the utility to establish a new task rather than query or delete an existing one42. |
| /tn | Defines the Task Name (e.g., "BubbleNews") to allow future referencing and modification42. |
| /tr | Specifies the Task Run path. This must encompass the executable binary and the target script, carefully wrapped in quotes to accommodate directory structures containing whitespaces42. |
| /sc | Defines the Schedule frequency (e.g., daily, hourly, onlogon)42. |
| /st | Establishes the specific Start Time using a 24-hour format (e.g., 08:00)42. |

By isolating the scheduling logic within a dedicated script, the application respects the core tenet of single-responsibility architecture, ensuring that the main aggregation pipeline remains entirely decoupled from operating system idiosyncrasies1.

## **System Resilience and Defensive Engineering**

BUBBLE NEWS operates in an environment characterized by extreme volatility: RSS feeds routinely go offline, APIs experience latency spikes, and web publishers constantly alter their DOM structures to prevent scraping1. Consequently, the software is engineered with defensive mechanisms to ensure continuous operation1.  
A critical architectural rule states that the failure of a singular component must not induce a catastrophic systemic collapse1. If an RSS endpoint times out, the feedparser library traps the socket error, logging a clear warning (e.g., \[WARNING\] Unable to access RSS feed) before gracefully resuming the iteration over the remaining URLs1. If newspaper3k encounters a website protected by complex JavaScript rendering or Cloudflare captchas, the HTML parsing will fail; rather than terminating, the system abandons deep extraction and falls back to the headline and summary natively provided by the RSS XML file1.  
In scenarios where the temporal constraints filter out every single article across the entire configuration—resulting in an empty execution queue—the system correctly identifies this as a valid operational state. It circumvents the Google Gemini processing phase entirely, directly triggering the SMTP transmission of a succinct email informing the user that no news events transpired within the preceding twelve hours1.  
Finally, the terminal output is engineered to be explicitly clear and non-verbose, utilizing standardized logging brackets (\[INFO\], \[OK\], \[WARN\], \[ERROR\]) to visually demark the successful transition through the six core execution phases (Loading, Reading, Filtering, Fetching, Processing, Sending), thereby offering immediate diagnostic clarity for manual executions1. Through these meticulous engineering tolerances, BUBBLE NEWS Version 0.1 Beta provides a highly secure, autonomous, and resilient news aggregation platform.

#### **Works cited**

> 1. BN Prompt.md  
> 2.   
> 3. BN Instructions.docx  
> 4. Securely storing configuration credentials in a Jupyter Notebook, [https://vickiboykis.com/2020/02/25/securely-storing-configuration-credentials-in-a-jupyter-notebook/](https://vickiboykis.com/2020/02/25/securely-storing-configuration-credentials-in-a-jupyter-notebook/)  
> 5. Using .env to securely store authentication keys in python, [https://blog.zanalytics.io/using-env-to-securely-store-authentication-keys-in-python-58489da7b248](https://blog.zanalytics.io/using-env-to-securely-store-authentication-keys-in-python-58489da7b248)  
> 6. Ensuring Secure Management of Secrets with Python-dotenv, [https://github.com/orgs/SajixInc/discussions/58](https://github.com/orgs/SajixInc/discussions/58)  
> 7. Structured outputs \- Interactions API \- Google AI for Developers, [https://ai.google.dev/gemini-api/docs/structured-output](https://ai.google.dev/gemini-api/docs/structured-output)  
> 8. How to store secrets using environment variables in Python, [https://www.thedataschool.co.uk/daniel-bostrom/how-to-store-environment-variables-in-python-without-them-being-visible-on-github-2/](https://www.thedataschool.co.uk/daniel-bostrom/how-to-store-environment-variables-in-python-without-them-being-visible-on-github-2/)  
> 9. Why are .env files considered secure if they are plain text files?, [https://discuss.python.org/t/why-are-env-files-considered-secure-if-they-are-plain-text-files/50452](https://discuss.python.org/t/why-are-env-files-considered-secure-if-they-are-plain-text-files/50452)  
> 10. .ENV — How to keep a secret (Python) | by Kimberly Benton \- Medium, [https://medium.com/@kimberly.d.benton/env-how-to-keep-a-secret-python-react-7cdf77848f88](https://medium.com/@kimberly.d.benton/env-how-to-keep-a-secret-python-react-7cdf77848f88)  
> 11. Using dotenv to Hide Sensitive Information in Python, [https://towardsdatascience.com/using-dotenv-to-hide-sensitive-information-in-python-77ab9dfdaac8/](https://towardsdatascience.com/using-dotenv-to-hide-sensitive-information-in-python-77ab9dfdaac8/)  
> 12. Why do people put the .env into gitignore? \- Stack Overflow, [https://stackoverflow.com/questions/43664565/why-do-people-put-the-env-into-gitignore](https://stackoverflow.com/questions/43664565/why-do-people-put-the-env-into-gitignore)  
> 13. Looking for a simple and slim method to store login data for a script, [https://www.reddit.com/r/learnpython/comments/1nzfkkn/looking\_for\_a\_simple\_and\_slim\_method\_to\_store/](https://www.reddit.com/r/learnpython/comments/1nzfkkn/looking_for_a_simple_and_slim_method_to_store/)  
> 14. Newspaper3k Guide \- Scrape Articles Using AI \- ScrapeOps, [https://scrapeops.io/python-web-scraping-playbook/newspaper3k/](https://scrapeops.io/python-web-scraping-playbook/newspaper3k/)  
> 15. Date Parsing — feedparser 5.2.0 documentation \- Pythonhosted.org, [https://pythonhosted.org/feedparser/date-parsing.html](https://pythonhosted.org/feedparser/date-parsing.html)  
> 16. python \- How do I parse an ISO 8601-formatted date and time?, [https://stackoverflow.com/questions/127803/how-do-i-parse-an-iso-8601-formatted-date-and-time](https://stackoverflow.com/questions/127803/how-do-i-parse-an-iso-8601-formatted-date-and-time)  
> 17. Parse datetime strings in Python with dateutil \- TestDriven.io, [https://testdriven.io/tips/44fef95e-e7ca-4da0-b14b-b5e3c8780036/](https://testdriven.io/tips/44fef95e-e7ca-4da0-b14b-b5e3c8780036/)  
> 18. Mastering Date Parsing in Python using dateutil | by Divas \- Medium, [https://medium.com/@divasthottungal/mastering-date-parsing-in-python-using-dateutil-c813bb4f4aeb](https://medium.com/@divasthottungal/mastering-date-parsing-in-python-using-dateutil-c813bb4f4aeb)  
> 19. How do I translate an ISO 8601 datetime string into a Python, [https://stackoverflow.com/questions/969285/how-do-i-translate-an-iso-8601-datetime-string-into-a-python-datetime-object](https://stackoverflow.com/questions/969285/how-do-i-translate-an-iso-8601-datetime-string-into-a-python-datetime-object)  
> 20. It's impossible to parse ISO-style and European-style dates ... \- GitHub, [https://github.com/dateutil/dateutil/issues/402](https://github.com/dateutil/dateutil/issues/402)  
> 21. dateutil.parser.isoparser — dateutil 2.7.5 documentation, [https://dateutil.readthedocs.io/en/2.7.5/\_modules/dateutil/parser/isoparser.html](https://dateutil.readthedocs.io/en/2.7.5/_modules/dateutil/parser/isoparser.html)  
> 22. parser — dateutil 3.9.0 documentation \- Read the Docs, [https://dateutil.readthedocs.io/en/stable/parser.html](https://dateutil.readthedocs.io/en/stable/parser.html)  
> 23. codelucas/newspaper: newspaper3k is a news, full-text, and article, [https://github.com/codelucas/newspaper](https://github.com/codelucas/newspaper)  
> 24. How To Scrape News Articles with Newspaper3k (Python), [https://www.scraperapi.com/blog/python-newspaper3k/](https://www.scraperapi.com/blog/python-newspaper3k/)  
> 25. SMTP failure with some servers, HELO requires fully qualified, [https://github.com/djcb/mu/issues/2867](https://github.com/djcb/mu/issues/2867)  
> 26. Controlled generation JSON output with predefined schema, [https://docs.cloud.google.com/vertex-ai/generative-ai/docs/samples/generativeaionvertexai-gemini-controlled-generation-response-schema-2](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/samples/generativeaionvertexai-gemini-controlled-generation-response-schema-2)  
> 27. Intro to Structured Output with the Gemini API \- Google Colab, [https://colab.research.google.com/github/GoogleCloudPlatform/generative-ai/blob/main/gemini/controlled-generation/intro\_controlled\_generation.ipynb](https://colab.research.google.com/github/GoogleCloudPlatform/generative-ai/blob/main/gemini/controlled-generation/intro_controlled_generation.ipynb)  
> 28. Structured output | Gemini Enterprise Agent Platform, [https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/capabilities/control-generated-output](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/capabilities/control-generated-output)  
> 29. CSS in HTML emails: What you need to know to get started \- Emma, [https://myemma.com/blog/css-in-html-emails-what-you-need-to-know-to-get-started/](https://myemma.com/blog/css-in-html-emails-what-you-need-to-know-to-get-started/)  
> 30. Python Send HTML Email: Tutorial with Code Snippets \[2026\], [https://mailtrap.io/blog/python-send-html-email/](https://mailtrap.io/blog/python-send-html-email/)  
> 31. Configuring and Sending Emails in Domino Using Python smtplib, [https://support.domino.ai/support/s/article/Sending-emails-in-python-using-smtplib-1718868040933](https://support.domino.ai/support/s/article/Sending-emails-in-python-using-smtplib-1718868040933)  
> 32. email.mime: Creating email and MIME objects from scratch, [https://docs.python.org/3/library/email.mime.html](https://docs.python.org/3/library/email.mime.html)  
> 33. Send Emails with Python smtplib \- Pybites, [https://pybit.es/articles/python-smtplib/](https://pybit.es/articles/python-smtplib/)  
> 34. What SMTP port should be used? Port 25, 587, or 465? \- Cloudflare, [https://www.cloudflare.com/learning/email-security/smtp-port-25-587/](https://www.cloudflare.com/learning/email-security/smtp-port-25-587/)  
> 35. Common SMTP Ports Explained (Port 25, 587 or 465), [https://wpmailsmtp.com/smtp-port/](https://wpmailsmtp.com/smtp-port/)  
> 36. SMTP STARTTLS Errors: Causes, Fixes & Secure Email \- Warmy Blog, [https://www.warmy.io/blog/smtp-starttls-errors-causes-fixes-how-to-ensure-secure-email-communication/](https://www.warmy.io/blog/smtp-starttls-errors-causes-fixes-how-to-ensure-secure-email-communication/)  
> 37. Email Alerts Fail to Work With STARTTLS \- Netgate Forum, [https://forum.netgate.com/topic/180343/email-alerts-fail-to-work-with-starttls](https://forum.netgate.com/topic/180343/email-alerts-fail-to-work-with-starttls)  
> 38. Which SMTP Port to Use? Understanding ports 25, 465, & 587, [https://www.mailgun.com/blog/email/which-smtp-port-understanding-ports-25-465-587/](https://www.mailgun.com/blog/email/which-smtp-port-understanding-ports-25-465-587/)  
> 39. Example code for sending an email via SMTP with TLS ... \- Github-Gist, [https://gist.github.com/jamescalam/93d915e4de12e7f09834ae73bdf37299](https://gist.github.com/jamescalam/93d915e4de12e7f09834ae73bdf37299)  
> 40. A Complete Guide to Using the STARTTLS Port for Email Encryption, [https://blog.mystrika.com/starttls-port/](https://blog.mystrika.com/starttls-port/)  
> 41. Sending mail from Python using SMTP \- Stack Overflow, [https://stackoverflow.com/questions/64505/sending-mail-from-python-using-smtp](https://stackoverflow.com/questions/64505/sending-mail-from-python-using-smtp)  
> 42. schtasks create \- Microsoft Learn, [https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/schtasks-create](https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/schtasks-create)  
> 43. windows\_task\_scheduler.py \- scripts \- GitHub, [https://github.com/aw-junaid/Python-System-Administration/blob/main/modules/Task%20Scheduling/scripts/windows\_task\_scheduler.py](https://github.com/aw-junaid/Python-System-Administration/blob/main/modules/Task%20Scheduling/scripts/windows_task_scheduler.py)  
> 44. Is there a way to add a task to the windows task scheduler via, [https://stackoverflow.com/questions/26160900/is-there-a-way-to-add-a-task-to-the-windows-task-scheduler-via-python-3](https://stackoverflow.com/questions/26160900/is-there-a-way-to-add-a-task-to-the-windows-task-scheduler-via-python-3)  
> 45. Schedule a Python Script using Windows Task ... \- Esri Community, [https://community.esri.com/t5/python-documents/schedule-a-python-script-using-windows-task/ta-p/915861](https://community.esri.com/t5/python-documents/schedule-a-python-script-using-windows-task/ta-p/915861)  
> 46. Setting up Windows Task Scheduler with (Python \+ PowerShell \+, [https://www.reddit.com/r/learnpython/comments/1e9vzth/setting\_up\_windows\_task\_scheduler\_with\_python/](https://www.reddit.com/r/learnpython/comments/1e9vzth/setting_up_windows_task_scheduler_with_python/)  
> 47. Solved: schtasks run task with parameters \- Experts Exchange, [https://www.experts-exchange.com/questions/27025515/schtasks-run-task-with-parameters.html](https://www.experts-exchange.com/questions/27025515/schtasks-run-task-with-parameters.html)