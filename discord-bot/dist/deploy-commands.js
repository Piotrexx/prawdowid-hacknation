import "dotenv/config";
import { REST, Routes } from "discord.js";
import { factCheckCommand } from "./factCheck.js";
const token = process.env.DISCORD_TOKEN;
const clientId = process.env.CLIENT_ID;
const guildId = process.env.GUILD_ID;
if (!token || !clientId) {
    throw new Error("Brak DISCORD_TOKEN albo CLIENT_ID w zmiennych środowiskowych (.env).");
}
const commands = [factCheckCommand.toJSON()];
const rest = new REST().setToken(token);
async function main() {
    // Rejestracja na serwerze (GUILD_ID) jest natychmiastowa – wygodna na czas developmentu.
    // Bez GUILD_ID rejestrujemy globalnie (propagacja do serwerów Discorda trwa do ~1h).
    const route = guildId ? Routes.applicationGuildCommands(clientId, guildId) : Routes.applicationCommands(clientId);
    const data = (await rest.put(route, { body: commands }));
    console.log(`Zarejestrowano ${data.length} komend(y) ${guildId ? `na serwerze ${guildId}` : "globalnie"}.`);
}
main().catch((error) => {
    console.error("Nie udało się zarejestrować komend:", error);
    process.exit(1);
});
//# sourceMappingURL=deploy-commands.js.map