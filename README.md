# alicebot
A simple discord bot

## Commands
* .access 
* .config
* .invite
* .ping
* .define
* .d
* .conversion
* .convert

## .access
```
  .access list
  .access set {command} {role}
  .access unset {command}
```
This command is used to restrict which roles are permitted to run specific bot commands. When set you must hold the mentioned role for the command to work.


## .config
```
    .config list
    .config get {key}
    .config set {key} {value}
    .config unset {key}
```
Alter the bot configuration for this server.

### .invite
Allows a user to generate a one person invite once every {invite_cooldown} to this server which will expire in {invite_timespan}

### .ping
Simple test command which checks that the bot is online.

### .define
```
    .define {word} "Meaning..."
```
Adds a word definition to the library for the .d command, set the meaning to an empty string to delete it.

### .d
```
    .d {word}
    .d list
```
Print the definition of a word from the library, or list all the words that are defined.

### .conversion
```
    .conversion list
    .conversion remove {fromunit} [subunit]
    .conversion {fromunit} {factor/formula} {tounit} [subunit]
```
Add a conversion calculation to the .convert command. {fromunit} is the name of
the unit we are converting from. {factor} is either a multiplication factor, or
it is a formula converting x the input value. [subunit] is used to
defferentiate between different substances that share the same units, and
{tounit} is the unit of the result.

``` Examples:
    .conversion pmol/l 3.671 pg/ml e2
    .conversion celsius "((x-32)*5)/9" fahrenheit
```

### .convert
```
    .convert list
    .convert {value} {unit} [subunit]
```
List all of the known conversions, or convert the given value of the given unit and optional subunit.

## Automated functions
Once per hour the bot will check the userlist for users that still have the role {autokick_hasrole} and have been on the server for {autokick_timelimit} it will kick them from your server giving the optional reason of {autokick_reason}.  This can be used to timeout new years who joined and were given an auto role by another bot but then failed to pass whatever gating or registration process you have that would have removed that role.

