export class Repository {
    async save(data: string) {
        console.log("Saving data:", data);
        return { success: true };
    }

    private unusedMethod() {
        console.log("I am dead code");
    }
}

export function helper() {
    const repo = new Repository();
    return repo.save("some data");
}
