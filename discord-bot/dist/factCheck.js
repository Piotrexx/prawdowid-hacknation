import { ChatInputCommandInteraction, Colors, EmbedBuilder, SlashCommandBuilder } from "discord.js";
import { BackendError, checkImage, checkText, checkUrl } from "./api.js";
const FRONTEND_URL = (process.env.FRONTEND_URL ?? "http://localhost:3000").replace(/\/$/, "");
const MAX_IMAGE_BYTES = 5_000_000;
const STATUS_LABELS = {
    completed: "Zakończone",
    needs_clarification: "Wymaga doprecyzowania",
    out_of_scope: "Poza zakresem",
    error: "Problem techniczny",
};
const VERDICT_COLORS = {
    potwierdzone: Colors.Green,
    falszywe: Colors.Red,
    wprowadzajace_w_blad: Colors.Orange,
    brak_wystarczajacych_dowodow: Colors.Grey,
    nie_podlega_weryfikacji: Colors.Grey,
};
export const factCheckCommand = new SlashCommandBuilder()
    .setName("fact-check")
    .setDescription("Sprawdź tekst, link albo zdjęcie pod kątem dezinformacji.")
    .addStringOption((option) => option.setName("tekst").setDescription("Tekst do sprawdzenia").setMaxLength(2000))
    .addStringOption((option) => option.setName("url").setDescription("Link do artykułu lub strony"))
    .addAttachmentOption((option) => option.setName("zdjecie").setDescription("Zdjęcie lub screenshot do sprawdzenia"));
function buildEmbed(result) {
    const embed = new EmbedBuilder().setTitle(`Wynik sprawdzenia: ${STATUS_LABELS[result.status]}`);
    if (result.status !== "completed") {
        embed.setColor(Colors.Grey);
        embed.setDescription(result.status_message ?? "Nie udało się przeprowadzić sprawdzenia.");
    }
    else {
        embed.setColor(result.verdict ? (VERDICT_COLORS[result.verdict] ?? Colors.Blurple) : Colors.Blurple);
        const confidence = result.confidence != null ? ` (${Math.round(result.confidence * 100)}% pewności)` : "";
        embed.setDescription(`**Werdykt: ${result.verdict_label ?? "—"}${confidence}**`);
        if (result.summary) {
            embed.addFields({ name: "Podsumowanie", value: result.summary.slice(0, 1024) });
        }
        if (result.justification) {
            embed.addFields({ name: "Uzasadnienie", value: result.justification.slice(0, 1024) });
        }
    }
    if (result.warnings.length > 0) {
        embed.addFields({
            name: "Ostrzeżenia",
            value: result.warnings
                .slice(0, 5)
                .map((w) => `• ${w.message}`)
                .join("\n")
                .slice(0, 1024),
        });
    }
    embed.setURL(`${FRONTEND_URL}/analiza/${result.id}`);
    embed.setFooter({ text: "Pełna analiza na stronie Prawdowid" });
    return embed;
}
export async function handleFactCheck(interaction) {
    const tekst = interaction.options.getString("tekst");
    const url = interaction.options.getString("url");
    const zdjecie = interaction.options.getAttachment("zdjecie");
    const provided = [tekst, url, zdjecie].filter((value) => value != null);
    if (provided.length !== 1) {
        await interaction.reply({
            content: "Podaj dokładnie jedno: `tekst`, `url` albo `zdjecie`.",
            ephemeral: true,
        });
        return;
    }
    await interaction.deferReply();
    try {
        let result;
        if (zdjecie != null) {
            if (zdjecie.size > MAX_IMAGE_BYTES) {
                await interaction.editReply("Zdjęcie jest za duże (limit 5 MB).");
                return;
            }
            const response = await fetch(zdjecie.url, { signal: AbortSignal.timeout(30_000) });
            const file = Buffer.from(await response.arrayBuffer());
            result = await checkImage(interaction.user.id, file, zdjecie.name, zdjecie.contentType ?? "image/png");
        }
        else if (url != null) {
            result = await checkUrl(interaction.user.id, url.trim());
        }
        else {
            result = await checkText(interaction.user.id, tekst.trim());
        }
        await interaction.editReply({ embeds: [buildEmbed(result)] });
    }
    catch (error) {
        const message = error instanceof BackendError
            ? error.message
            : "Nie udało się połączyć z serwisem sprawdzającym. Spróbuj ponownie później.";
        await interaction.editReply(message);
    }
}
//# sourceMappingURL=factCheck.js.map