# vllm-deps-autofiler
automatically files jira deps, dude.

# stuff I did...

Create a JIRA API PAT by going to your profile and then making a personal access token. Save it in your .env file here.

```
source .env
docker run -it --rm \
  -v $PWD/.jira-cli:/root/.config/.jira:Z \
  -e JIRA_API_TOKEN=$JIRA_API_TOKEN \
  ghcr.io/ankitpokhrel/jira-cli:latest
```

First time through, do `jira init` and add your URL and username.

It should save in the local `.jira-cli` dir here.

