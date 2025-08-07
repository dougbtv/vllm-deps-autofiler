Notes of what I need to do:

We're making descriptions and instructions for submitting tickets automatically about updated packages in vLLM

See: example-ticket for instructions

We're going to use jira cli to emulate (but not actually) a clone of https://issues.redhat.com/browse/AIPCC-1, which is that example epic.

It has assignee, components and labels that we care about.

We're first looking at the diff... and to determine each package.

For each item in the diff we need to create a description based on the example ticket.

It's important to note these things as basics for the ticket:

```
The tickets are pre-emptive of the release of vLLM v0.10.1
There may still be further changes when v0.10.1 is cut.
The reasons that we need the packages is because they've been updated in upstream vLLM and we need them for the next midstream and later downstream release.
```

For each change in the diff, you're going to have to make generate kind of a file that we can read programatically. And generate the body descriptions based on the template.

We'll put those files in `./ticket_text`

It should have, for example:

```
package_name: transformers
package_version: v0.x.z
body_description: <from template but fleshed out>
```

Then we'll need a script that can, with a docker image like:

```
source .env
docker run -it --rm \
  -v $PWD/.jira-cli:/root/.config/.jira:Z \
  -e JIRA_API_TOKEN=$JIRA_API_TOKEN \
  ghcr.io/ankitpokhrel/jira-cli:latest
```

Run commands for the jira cli that we're using.


It has a template found in example-ticket.txt

Epic title should be: builder: <packagename> package update request

Here I used "dougtest" as the example packagename.

the -b is where we'll put the body.


I tested creating one like this:

jira epic create \
  -p AIPCC \
  -n "builder: dougtesting package update request" \
  -s "builder: dougtesting package update request" \
  -b "Auto-generated from deps-autofiler tool" \
  --no-input

I get:

```
~ # jira epic create \
>   -p AIPCC \
>   -n "builder: dougtesting package update request" \
>   -s "builder: dougtesting package update request" \
>   -b "Auto-generated from deps-autofiler tool" \
>   --no-input

✓ Epic created
https://issues.redhat.com/browse/AIPCC-4193
```

We then need to edit that:

```
jira issue edit AIPCC-4192 \
  -s "builder: dougtesting package update request" \
  -y Normal \
  -a rh-ee-raravind \
  -l package \
  -C "Accelerator Enablement" \
  -C "Application Platform"
```

To properly set the assignee and label and components.

What we'll need to do is have a script that we can run that walks through all of the ./ticket_texts and runs the commands using the a docker run for each I think, or some way to 

I think we can probably write this in python, and potentially use jinja for formatting.

This should default to a dry run, and! ...We need a pretty way to look at a preview of what we'll be submitting.
