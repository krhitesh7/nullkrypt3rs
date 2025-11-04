// vulnerable.go
package main

import (
	"fmt"
	"log"
	"net/http"
	"strings"
)

type Document struct {
	ID      string
	OwnerID string
	Content string
}

var docs = map[string]Document{
	"1": {ID: "1", OwnerID: "alice", Content: "Alice's secret notes"},
	"2": {ID: "2", OwnerID: "bob", Content: "Bob's top secret"},
}

func main() {
	http.HandleFunc("/docs/", docHandler) // GET /docs/{id}
	log.Println("Starting vulnerable server on :8080")
	log.Fatal(http.ListenAndServe(":8080", nil))
}

func docHandler(w http.ResponseWriter, r *http.Request) {
	id := strings.TrimPrefix(r.URL.Path, "/docs/")
	if id == "" {
		http.Error(w, "missing id", http.StatusBadRequest)
		return
	}

	doc, ok := docs[id]
	if !ok {
		http.NotFound(w, r)
		return
	}

	fmt.Fprintf(w, "Document ID: %s\nOwner: %s\nContent: %s\n", doc.ID, doc.OwnerID, doc.Content)
}
