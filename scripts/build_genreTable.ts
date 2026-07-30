import * as fs from "node:fs";

//ARGUMENTS
let inputFile = String.raw`D:\Documents\Programming\mopidy\mopidy-eboplayer\configFiles\musicGenres.md`;
let outputFileName = String.raw`D:\Documents\Programming\mopidy\mopidy-eboplayer\scripts\genres.sql`;

class Writer {
    private outFile: fs.WriteStream;

    constructor(outFile: fs.WriteStream) {
        this.outFile = outFile;
    }

    indent: number = 0;
    write(text: string, indent?: number) {
        let indentString = indent ? ' '.repeat(indent) : '';
        this.outFile.write(`${indentString}${text}`);
    }

    writeLine(line: string, indent: number) {
        this.write(`${line}\n`, indent);
    }
}

main();

interface LineDef {
    indent: number,
    name: string
}

function main() {
    let text = fs.readFileSync(inputFile, 'utf8');
    let lines = text.split("\n").map(line => line.replace("\r", ""));

    let writer = new Writer(fs.createWriteStream(outputFileName));

    writer.write(`insert into genre_defs (name, child, sequence, level) values`, 0);

    let parentStack: LineDef[] = [];
    let indent: number = 0;
    let level = -1;
    let prevLine: LineDef | null = null;
    let sequence = 0;
    let comma = "";
    lines
        .filter(line => line.trim().length > 0)
        .forEach(line => {
            let parsedLine = parseLine(line);
            let parent: LineDef | null = null;
            if(parsedLine.indent > indent) {
                if(prevLine)
                    parentStack.push(prevLine);
                indent = parsedLine.indent;
                level++;
            } else {
                while (parsedLine.indent < indent) {
                    let newLevel = parentStack.pop();
                    if(!newLevel)
                        break;
                    if(newLevel.indent < parsedLine.indent) { //oops, we went too far back.
                        parentStack.push(newLevel);
                        break;
                    }
                    indent = newLevel.indent;
                    level--;
                }
            }
            if(parentStack.length)
                parent = parentStack[parentStack.length - 1];
            if(parent)
                writeInsert(writer, parent.name, parsedLine.name, sequence, level, comma);
                // writer.writeLine(`-- insert into genre_defs (name, child, sequence) values('${parent.name}', '${parsedLine.name}', ${sequence});`, 0);
            else
                writeInsert(writer, parsedLine.name, null, sequence, level, comma);
                // writer.writeLine(`insert into genre_defs (name, child, sequence) values('${parsedLine.name}', null, ${sequence});`, 0);

            prevLine = parsedLine;
            sequence++;
            comma = ",";
        });
    writer.writeLine(";", 0);
}

function writeInsert(writer: Writer, name: string, child: string | null, sequence: number, level: number, comma: string) {
    name = name.replace(/'/g, "''");
    if(child) {
        child = child?.replace(/'/g, "''");
        writer.write(`${comma}\n('${name}', '${child}', ${sequence}, ${level})`, 0);
    } else
        writer.write(`${comma}\n('${name}', null, ${sequence}, ${level})`, 0);
}

function parseLine(line: string): LineDef {
    if(line.startsWith("# "))
        return {indent: 1, name: line.substring(2).trim()};
    if(line.startsWith("## "))
        return {indent: 2, name: line.substring(3).trim()};
    if(line.startsWith("### "))
        return {indent: 3, name: line.substring(4).trim()};
    if(line.startsWith("#### "))
        return {indent: 4, name: line.substring(5).trim()};
    let leadingSpaces = line.search(/\S/);
    return {indent: leadingSpaces+100, name: line.substring(leadingSpaces).trim()};
}