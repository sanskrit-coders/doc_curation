<xsl:stylesheet
        version="2.0"
        xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
        xmlns:tei="http://www.tei-c.org/ns/1.0"
        xpath-default-namespace="http://www.tei-c.org/ns/1.0">

    <xsl:import href="../../../../doc_curation/tei_xsl/markdown/tei-to-markdown.xsl"/>
    <xsl:template match="note">
        <xsl:text>+++(</xsl:text>
        <xsl:apply-templates/>
        <xsl:text>)+++</xsl:text>
    </xsl:template>
    <xsl:template match="fn[@marker]">
        <xsl:text>[</xsl:text>
        <xsl:value-of select="fn/@marker" />
        <xsl:text>]</xsl:text>
    </xsl:template>
    <xsl:template match="fn[@n]">
        <xsl:text>[</xsl:text>
        <xsl:value-of select="fn/@n" />
        <xsl:text>]: </xsl:text>
    </xsl:template>
    <xsl:template match="pb[@n]">
        <xsl:text>{</xsl:text>
        <xsl:value-of select="fn/@n" />
        <xsl:text>}</xsl:text>
    </xsl:template>
</xsl:stylesheet>
