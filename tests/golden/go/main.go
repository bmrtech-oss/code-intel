package main

import "fmt"

type Logger struct{}

func (l *Logger) Log(message string) {
    fmt.Println(message)
    l.deepLog1(message)
}

func (l *Logger) deepLog1(message string) {
    l.deepLog2(message)
}

func (l *Logger) deepLog2(message string) {
    fmt.Printf("LOG: %s\n", message)
}

func DeadGoFunction() {
    fmt.Println("No one calls me")
}

func main() {
    logger := &Logger{}
    logger.Log("Hello from Go")
}
