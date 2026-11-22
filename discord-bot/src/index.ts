import "dotenv/config";
import { Client, Events, GatewayIntentBits } from "discord.js";
import { factCheckCommand, handleFactCheck } from "./factCheck.js";

const token = process.env.DISCORD_TOKEN;
if (!token) {
  throw new Error("Brak DISCORD_TOKEN w zmiennych środowiskowych (.env).");
}

const client = new Client({ intents: [GatewayIntentBits.Guilds] });

client.once(Events.ClientReady, (readyClient) => {
  console.log(`Zalogowano jako ${readyClient.user.tag}`);
});

client.on(Events.InteractionCreate, async (interaction) => {
  if (!interaction.isChatInputCommand()) return;
  if (interaction.commandName !== factCheckCommand.name) return;

  try {
    await handleFactCheck(interaction);
  } catch (error) {
    console.error("Nieoczekiwany błąd obsługi /fact-check:", error);
  }
});

void client.login(token);
